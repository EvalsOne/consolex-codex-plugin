#!/usr/bin/env python3
"""Codex/DSH adapters around the same ConsoleX client used by Claude Code.

Only normalized runtime events enter here. No dependency on either product's
private transcript format; the runtimes supply final text and tool results.
`save` sends this session's journal, which is built from the same events.
The package builder puts this module and consolex_core.py beside each other.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

_path = Path(__file__).with_name('consolex_core.py')
_spec = importlib.util.spec_from_file_location('consolex_core', _path)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

RUNTIMES = {'codex': 'Codex', 'deepseek_harness': 'DeepSeek Harness'}
QUESTION_TOOLS = {'request_user_input', 'request_user_input_async', 'ask_user_question'}
CONTROL_TOOLS = QUESTION_TOOLS | {'skill', 'Skill', 'update_plan'}
COMMAND_NAMES = '|'.join(name.split(':', 1)[1] for name in list(core.COMMANDS) + list(core.SCHEDULE_COMMANDS))
# `/consolex-tasks`: the command Skills in ~/.agents/skills, which DeepSeek Harness lists as slash commands too.
COMMAND = re.compile(r'^\s*(?:\$(?:consolex:)?consolex-|/consolex[-: ])(%s)\b\s*(.*)' % COMMAND_NAMES, re.S)
TASK = re.compile(r'^\s*(?:\$|/)(cx-[a-z0-9-]{1,70})(?![a-z0-9-])')
# A Skill picked from Codex's menu arrives as a link to its SKILL.md: `[$consolex-tasks](/Users/me/.agents/skills/…)`.
SKILL_LINK = re.compile(r'\[(\$[A-Za-z0-9][A-Za-z0-9:_-]*)\]\([^)\n]*\)')
SPAWN_REFRESH = None  # Tests replace the detached refresher; None starts the real one.


def plain_prompt(prompt):
    """The prompt as typed: a picked Skill becomes `$name`, so it is a command and no local path is saved."""
    return SKILL_LINK.sub(r'\1', prompt)


def environment(env, runtime):
    if runtime not in RUNTIMES:
        raise ValueError('Unsupported runtime')
    env = {**env, 'CONSOLEX_RUNTIME': runtime}
    env['CONSOLEX_DATA'] = env.get('CONSOLEX_DATA') or env.get('PLUGIN_DATA') or core.consolex_home(env)
    return env


def _context_text(output):
    return ((output or {}).get('hookSpecificOutput') or {}).get('additionalContext', '')


def _native_text(text, runtime):
    if runtime not in RUNTIMES:
        raise ValueError('Unsupported runtime')
    return core.native_text(text, runtime)  # shared with the Codex MCP server's consolex_command tool


def adapt(output, runtime):
    if not output:
        return None
    output = dict(output)
    for key in ('reason', 'systemMessage'):
        if isinstance(output.get(key), str):
            output[key] = _native_text(output[key], runtime)
    if output.get('hookSpecificOutput'):
        output['hookSpecificOutput'] = dict(output['hookSpecificOutput'])
        output['hookSpecificOutput']['additionalContext'] = _native_text(_context_text(output), runtime)
    return output


def _answer(response):
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            return False
    if not isinstance(response, dict) or response.get('isError') or response.get('is_error'):
        return False
    answers = response.get('answers')
    if isinstance(answers, dict):
        return any(isinstance(value, dict) and value.get('answers') for value in answers.values())
    if isinstance(answers, list):
        return any(isinstance(value, dict) and (value.get('selected') or value.get('custom')) for value in answers)
    # MCP/text wrappers still carry structured answers as text blocks.
    return any(_answer(part.get('text', '')) for part in response.get('content', []) if isinstance(part, dict))


def _evidence(marker, data):
    notes = marker.setdefault('tool_notes', {'dropped': 0, 'images': 0, 'clipped': 0})
    name = str(data.get('tool_name') or '')
    if name in CONTROL_TOOLS or name.startswith('mcp__codex_app__'):
        return
    inputs = core.redact(core._tool_input(name, data.get('tool_input')))
    response = data.get('tool_response')
    if isinstance(response, dict) and isinstance(response.get('content'), list):
        text, images = core._result_text(response['content'], None)
    else:
        text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        images = 0
    inputs, clipped_input = core._clip(inputs, core.MAX_TOOL_INPUT_CHARS)
    redacted = core.redact(text)
    text, clipped = core._clip(redacted, core.MAX_TOOL_OUTPUT_CHARS)
    notes['images'] += images
    notes['clipped'] += int(clipped or clipped_input)
    records = marker.setdefault('tools', [])
    call_id = str(data.get('tool_use_id') or '')
    # Tool completion callbacks may be redelivered by a carrier.
    if call_id and any(item.get('_id') == call_id for item in records):
        return
    failed = bool(data.get('is_error') or isinstance(response, dict) and
                  (response.get('is_error') or response.get('isError')))
    record = {'name': name[:200], 'input': inputs, 'output': text, 'clipped': clipped,
              'is_error': failed, '_id': call_id}
    # Retain a bounded, redacted complete output locally only when opted in.
    if (marker.get('recover_evidence') is True and clipped and not failed and not images
            and not clipped_input and len(redacted) <= 60000
            and sum(len(item.get('_recovery_output', '')) for item in records) + len(redacted) <= 120000):
        record['_recovery_output'] = redacted
    records.append(record)
    while len(records) > core.MAX_TOOL_RECORDS or sum(len(i['input']) + len(i['output']) for i in records) > core.MAX_TOOL_TOTAL_CHARS:
        records.pop(0)
        notes['dropped'] += 1


def _activate_from_tool(data, env, http):
    name = data.get('tool_name')
    args = data.get('tool_input') or {}
    candidate = args.get('name') or args.get('skill') if isinstance(args, dict) else None
    if name in ('skill', 'Skill') and candidate:
        folder = core.find_skill_dir(str(candidate).split(':')[-1], env, data.get('cwd') or os.getcwd())
        if folder:
            return core.activate(data, env, folder, http=http)
    # Reading/editing SKILL.md is also how maintenance chats inspect a task. It is
    # not an invocation. Codex task activation comes from the owner's leading
    # $cx-… / picked Skill or $consolex-start, never arbitrary shell/file input.
    return None


# ---------------------------------------------------------------- session journal (for save)
#
# `save` sends the owner's messages, the final reply and the tool records of the whole session. Claude Code
# keeps a transcript for that; here they come only from the runtime's own events, so every session keeps a
# small journal beside its marker. It stays on this computer (0600, keys masked, capped like the upload) and
# is removed after a week without activity; nothing is sent unless the owner runs the save command.

def _journal_path(env, session_id):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', str(session_id or ''))[:128]
    return os.path.join(os.path.dirname(core._state_dir(env)), 'journal', safe + '.json') if safe else None


def load_journal(env, session_id):
    path = _journal_path(env, session_id)
    journal = core._read_json(path, None) if path else None
    if isinstance(journal, dict) and journal.get('session_id') == str(session_id):
        return journal
    return {'session_id': str(session_id or ''), 'started_at': time.time(), 'messages': [], 'reply': '', 'model': None}


def save_journal(env, journal):
    path = _journal_path(env, journal.get('session_id'))
    if not path:
        return
    if not os.path.exists(path):
        _sweep(env, os.path.dirname(path))  # A new session: drop what week-old sessions left behind.
    core._write_private(path, journal)


def _sweep(env, journal_dir):
    for folder in (core._state_dir(env), journal_dir):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            full = os.path.join(folder, name)
            try:
                if time.time() - os.path.getmtime(full) > core.MARKER_TTL_SECONDS:
                    os.remove(full)
            except OSError:
                pass


def _journal_prompt(env, data, prompt, *, command, synthetic):
    """An owner's prompt; ConsoleX commands and plugin continuations are not the owner's request."""
    if not data.get('session_id') or synthetic:
        return
    journal = load_journal(env, data['session_id'])
    if command:
        # The reply to a ConsoleX command only relays its result; it is not the session's result.
        journal['command_turn'] = data['prompt_id']
    else:
        journal.pop('command_turn', None)
        _note_skills(journal, _SKILL_MENTION.findall(prompt or ''))  # `$name` loads a Skill in Codex
        if prompt:
            messages = journal.setdefault('messages', [])
            messages.append(core._clip(core.redact(prompt), core.MAX_SAVED_MESSAGE_CHARS)[0])
            del messages[:-core.MAX_SAVED_MESSAGES]
    if data.get('model') and not journal.get('model'):
        journal['model'] = str(data['model'])[:128]  # Until a reply names the model that wrote it.
    save_journal(env, journal)


def _journal_reply(env, data, *, report):
    """The latest reply that answers the owner, not one that relays a command or reports a ConsoleX check."""
    if not data.get('session_id'):
        return
    journal = load_journal(env, data['session_id'])
    reply = data.get('last_assistant_message')
    if not report and data['prompt_id'] != journal.get('command_turn') and isinstance(reply, str) and reply.strip():
        journal['reply'] = core._clip(core.redact(reply.strip()), core.MAX_SAVED_REPLY_CHARS)[0]
        if data.get('model'):
            journal['model'] = str(data['model'])[:128]
    save_journal(env, journal)


# A Skill the agent read: Codex reads a Skill's SKILL.md with a shell command; DSH loads one with its Skill tool.
_SKILL_FILE = re.compile(r'(/[^\s"\'`]*?/skills/[^/\s"\'`]+)/SKILL\.md')
SKILL_TOOLS = ('Skill', 'skill', 'load_skill', 'skills_load')
_SKILL_MENTION = re.compile(r'(?:^|\s)\$([A-Za-z0-9][A-Za-z0-9._-]{1,127})\b')
MAX_JOURNAL_SKILLS = 30


def _note_skills(journal, values):
    """Remember Skills this session used (folders or names), latest last, for /consolex:save."""
    skills = journal.setdefault('skills', [])
    for value in values:
        value = str(value or '').strip()
        if not value or value.startswith(('consolex', 'cx-')) or os.path.basename(value).startswith(('consolex', 'cx-')):
            continue
        if value in skills:
            skills.remove(value)
        skills.append(value)
    del skills[:-MAX_JOURNAL_SKILLS]


def _skills_in_tool(data):
    name = str(data.get('tool_name') or '')
    tool_input = data.get('tool_input')
    if name in SKILL_TOOLS and isinstance(tool_input, dict):
        return [tool_input.get('skill') or tool_input.get('name') or '']
    text = tool_input if isinstance(tool_input, str) else json.dumps(tool_input, ensure_ascii=False)
    return _SKILL_FILE.findall(text or '')


def _journal_tool(env, data):
    if not data.get('session_id'):
        return
    journal = load_journal(env, data['session_id'])
    # Which Skills it read is kept apart from the tool records (capped at 80), so an early read is never lost.
    _note_skills(journal, _skills_in_tool(data))
    if not _evidence_off(env):
        _evidence(journal, data)
    save_journal(env, journal)


def _evidence_off(env):
    return str(env.get('CONSOLEX_TOOL_EVIDENCE', '')).lower() in ('off', '0', 'false', 'no')


def _records(holder):
    return [{k: v for k, v in item.items() if not k.startswith('_')} for item in holder.get('tools', [])]


def _save_inputs(env, data):
    """What `save` sends, from this session's journal (never from another runtime's log)."""
    journal = load_journal(env, data.get('session_id'))
    data['session_messages'] = list(journal.get('messages') or [])
    data['final_reply'] = journal.get('reply') or ''
    data['model'] = journal.get('model') or data.get('model')
    data['tools'] = _records(journal)
    data['tool_notes'] = journal.get('tool_notes', {})
    data['skills_read'] = list(journal.get('skills') or [])


NO_EXECUTION = ('This conversation has no stage-check execution for this ConsoleX task. Start the task here first (/cx-… '
                'or /consolex:start), then hand its stages in; another conversation\'s execution_id cannot be used.')


def _native_execution(env, data, need_own=False):
    """(execution id, marker, problem) for a DSH native ConsoleX tool call.

    The server binds an execution to its owner, task and computer, not to the conversation, so these tools (the plugin's
    own) do: an execution id is only ever this conversation's own, the one its session marker got when it started this
    task. A supplied id must be that one, for the task the call names; a conversation that did not start the task, a
    foreign id or another task is refused. Left out, the conversation's own is filled in. `need_own`: the call needs an
    execution (consolex_checkpoint); otherwise a conversation without stage checks calls without one, as before.
    """
    given = data.get('execution_id') if isinstance(data.get('execution_id'), str) and data.get('execution_id') else None
    marker = core.load_marker(env, data.get('session_id'))
    own = marker.get('execution_id') if marker and marker.get('checkpoint_required') else None
    if not own:
        if given or need_own:
            return None, marker, NO_EXECUTION
        return None, marker, ''
    config, _ = core._task_ref(env, data.get('task'), data.get('cwd'))
    same_task = bool(config) and config.get('task_uuid') == marker.get('task_uuid')
    if given and (given != own or not same_task) or need_own and not same_task:
        return None, marker, NO_EXECUTION + (' This conversation\'s execution for its own task is "%s".' % own if same_task else '')
    return own, marker, ''


def _native_stage_tool(data, env, http):
    """DSH's native consolex_checkpoint: a stage handed in, or where the stages stand (core.checkpoint_tool)."""
    execution_id, _, problem = _native_execution(env, data, need_own=True)
    if problem:
        return {'text': _native_text(problem, env['CONSOLEX_RUNTIME']), 'is_error': True}
    text, is_error = core.checkpoint_tool(env, data.get('task'), execution_id, data.get('operation'), data.get('stage_key'),
                                          data.get('text'), http=http, cwd=data.get('cwd'), session_id=data.get('session_id'))
    return {'text': core.command_text(text, env) if is_error else text, 'is_error': is_error}


def _native_task_tool(data, env, http):
    """DSH's native consolex_run_task_tool. In a conversation doing a task with stage checks the call carries the
    execution id and gets the same early look as a Claude Code or Codex hook gives (the server checks again)."""
    execution_id, marker, problem = _native_execution(env, data)
    if problem:
        return {'text': _native_text(problem, env['CONSOLEX_RUNTIME']), 'is_error': True}
    if marker and marker.get('checkpoint_required'):
        tool_input = {key: data[key] for key in ('task', 'tool', 'arguments') if key in data}
        if execution_id:
            tool_input['execution_id'] = execution_id
        guarded = core.checkpoint_hook({'hook_event_name': 'PreToolUse', 'session_id': data.get('session_id'),
                                        'cwd': data.get('cwd'), 'tool_name': core.RUN_TASK_TOOL,
                                        'tool_input': tool_input}, env, http=http)
        hook = (guarded or {}).get('hookSpecificOutput') or {}
        if hook.get('permissionDecision') == 'deny':
            return {'text': _native_text(str(hook.get('permissionDecisionReason') or 'ConsoleX stage check blocked this action.'),
                                         env['CONSOLEX_RUNTIME']), 'is_error': True}
    text, is_error = core.run_task_tool(env, data.get('task'), data.get('tool'), data.get('arguments'),
                                        data.get('session_id'), http=http, cwd=data.get('cwd'), execution_id=execution_id)
    return {'text': core.command_text(text, env) if is_error else text, 'is_error': is_error}


def task_tool_event(data, env, http=core.http_json):
    """DSH's native ConsoleX tools: {text, is_error}. The session id records the calls against this conversation,
    so a delivery's check sees them as calls ConsoleX ran itself."""
    if data.get('hook_event_name') == 'ConsoleXCheckpoint':
        return _native_stage_tool(data, env, http)
    if data.get('hook_event_name') == 'ConsoleXCommand':
        # The user asked in plain words for a ConsoleX command (add, remove, status …): the same result as typing it.
        text, is_error = core.command_for_agent(env, data.get('command'), data.get('arguments'), data.get('session_id'),
                                                data.get('cwd'), http=http)
        return {'text': text, 'is_error': is_error}
    if data.get('hook_event_name') == 'ConsoleXRenameSkill':
        name, problem = core.rename_task_skill(env, data.get('skill'), data.get('name'), data.get('cwd'))
        return {'text': problem or _native_text('Renamed. The task Skill is now /%s.' % name, env['CONSOLEX_RUNTIME']),
                'is_error': bool(problem)}
    if data.get('hook_event_name') == 'ConsoleXSave':
        # Step two of /consolex save: the session with the task's main skill, read from disk.
        text, is_error = core.save_session(env, data.get('save_id'), data.get('skill_path'), data.get('rules'),
                                           data.get('name'), http=http, result_id=data.get('result_id'))
        return {'text': _native_text(text, env['CONSOLEX_RUNTIME']), 'is_error': is_error}
    if data.get('hook_event_name') == 'ConsoleXTaskTools':
        text, is_error = core.task_tools_reply(env, data.get('task'), http=http, cwd=data.get('cwd'))
        return {'text': text, 'is_error': is_error}
    return _native_task_tool(data, env, http)


def handle(data, env, runtime, http=core.http_json):
    env = environment(env, runtime)
    if data.get('hook_event_name') in ('ConsoleXTaskTools', 'ConsoleXRunTaskTool', 'ConsoleXRenameSkill', 'ConsoleXCommand',
                                       'ConsoleXSave', 'ConsoleXCheckpoint'):
        return task_tool_event(data, env, http=http)
    data = dict(data)
    data['prompt_id'] = str(data.get('turn_id') or data.get('prompt_id') or 'turn')
    # Never ask the Claude transcript parser to interpret another runtime's log.
    data.pop('transcript_path', None)
    event = data.get('hook_event_name')
    if event == 'Stop':
        data['_stop_deadline'] = time.monotonic() + core.STOP_CHECK_BUDGET
    marker = core.load_marker(env, data.get('session_id'))
    if event == 'SessionStart':
        core.on_session_start(data, env, spawn=SPAWN_REFRESH, note=False)
        return None
    if event in ('SessionEnd', 'Interrupt'):
        core.SESSION_TIMEOUT = 2
        core.session_state(data, env, 'end' if event == 'SessionEnd' else 'idle', http=http)
        return None
    if event == 'UserPromptSubmit':
        prompt = plain_prompt(str(data.get('prompt') or '')).strip()
        # Stop-generated continuation is not a human answer, even if Codex
        # delivers it through UserPromptSubmit with a new turn id.
        tag = (marker or {}).get('continuation_tag')
        synthetic = bool(data.get('synthetic') or tag and tag in prompt)
        if marker:
            if not synthetic:
                marker.pop('awaiting_owner', None)
                marker['unattended'] = core.unattended(data, env, marker)
                marker.pop('review_gate', None)
                marker.pop('continuation_tag', None)
                marker.pop('continuation_chain', None)
                marker.pop('delivery_event', None)
                marker.pop('recovery_overrides', None)
                for item in marker.get('tools') or []:
                    item.pop('_recovery_output', None)
                # A new owner turn takes a fresh opt-in snapshot. If the task
                # was disabled or the server is unavailable, do not retain the
                # additional local evidence.
                _, config = core._session_config(env, data)
                core.refresh_recovery_preference(marker, config, env, http=http)
                marker['owner_answered_at'] = time.time()
                core.save_marker(env, marker)
            core.heartbeat(data, env, http=http)
        # A Codex app scheduled run: the app puts the automation's name and id above the saved prompt.
        schedule_id, body = core.codex_automation(prompt)
        if runtime == 'codex':
            # A Codex app scheduled run starts, or an automation changed since the last sync: ConsoleX hears this
            # computer's schedules (in the background).
            core.sync_schedules_if_changed(env, force=bool(schedule_id))
        match = COMMAND.match(body)
        journal_path = _journal_path(env, data.get('session_id'))
        if journal_path and not os.path.exists(journal_path):
            # A session's first prompt: its start, where a runtime has no SessionStart event (refresh is hourly at most).
            core.on_session_start(data, env, spawn=SPAWN_REFRESH, note=False)
        _journal_prompt(env, data, prompt, command=bool(match), synthetic=synthetic)
        if match:
            if match[1] == 'check' and marker:
                data['last_assistant_message'] = marker.get('last_assistant_message', '')
                data['tools'] = _records(marker)
                data['tool_notes'] = marker.get('tool_notes', {})
            if match[1] == 'save':
                _save_inputs(env, data)
            if match[1] == 'start':
                output, task = core.start_task(data, env, match[2], http=http)
                if task:
                    # Starting a task asks for work: keep its request and delivery when saving this session.
                    _journal_prompt(env, data, prompt, command=False, synthetic=synthetic)
                    if runtime == 'deepseek_harness':
                        output['consolexTask'] = {'name': task['name']}
            else:
                handler = core._command_handler('consolex:' + match[1], env)
                output = handler(data, env, match[2], http=http) if handler else core._context(data, (
                    'ConsoleX: scheduled runs are set up in the Codex app or the Claude desktop app; %s has no scheduler. '
                    'Tell the user in one line.') % RUNTIMES[runtime])
                if match[1] == 'save' and data.get('consolex_save_id') and runtime == 'deepseek_harness':
                    # A DSH command never reaches the model: the plugin wakes the agent for step two.
                    output = {**output, 'consolexSave': {'id': data['consolex_save_id']}}
            return adapt(output, runtime)
        match = TASK.search(body)
        if match:
            folder = core.find_skill_dir(match[1], env, data.get('cwd') or os.getcwd())
            if folder:
                return adapt(core.activate(data, env, folder, http=http), runtime)
        # A task added here after the owner saved it in ConsoleX (/consolex:save): said with the next plain prompt,
        # since these runtimes show nothing from a session start.
        guarded = core.checkpoint_hook(data, env, http=http)
        if guarded:
            return adapt(guarded, runtime)
        note = core.take_install_note(env, {**data, 'hook_event_name': 'UserPromptSubmit'})
        return adapt(note, runtime) if note else None
    if event == 'PreToolUse':
        guarded = core.checkpoint_hook(data, env, http=http)
        if guarded:
            return adapt(guarded, runtime)
    if event in ('PreToolUse', 'PostToolUse') and data.get('tool_name') in QUESTION_TOOLS:
        if marker:
            if event == 'PreToolUse':
                core.session_state(data, env, 'ask', http=http)
            elif _answer(data.get('tool_response')):
                marker.pop('awaiting_owner', None)
                marker.pop('review_gate', None)
                marker.pop('continuation_chain', None)
                marker.pop('delivery_event', None)
                marker['owner_answered_at'] = time.time()
                core.save_marker(env, marker)
                core.heartbeat(data, env, http=http)
        return None
    if event == 'PostToolUse' and runtime == 'codex' and core.is_codex_schedule_tool(data.get('tool_name')):
        # The agent created, changed or deleted a Codex app scheduled task: ConsoleX hears it at once.
        return adapt(core.on_codex_schedule_changed(data, env, http=http), runtime)
    if event == 'PostToolUse':
        # A tool that names a skill folder may have edited it (a patch, a shell command): synced when the turn ends.
        core.note_method_edit(env, data.get('session_id'), core.skill_paths_in(data.get('tool_input') or {}, data.get('cwd')))
        output = _activate_from_tool(data, env, http)
        marker = core.load_marker(env, data.get('session_id'))
        if marker and not _evidence_off(env):
            _evidence(marker, data)
            core.save_marker(env, marker)
        _journal_tool(env, data)
        return adapt(output, runtime)
    if event != 'Stop':
        return None
    # The turn ends: skills it edited reach ConsoleX now, as one version each (the task's own skill is synced by the
    # check below for a task session).
    # The turn ConsoleX continued to report a check result: Codex's review gate, or DSH's report step.
    # Older clients set the review gate even when the plugin itself requested a
    # revision. Recover that pending continuation as well as new ones.
    pending = (marker or {}).get('continuation_chain')
    if marker and not pending and marker.get('review_gate'):
        pending_chains = [key for key, chain in (marker.get('chains') or {}).items() if chain.get('sent_back')]
        if len(pending_chains) == 1:
            pending = pending_chains[0]
    if pending and marker and (marker.get('chains') or {}).get(pending, {}).get('sent_back'):
        marker.pop('review_gate', None)
        marker['continuation_chain'] = pending
        data['prompt_id'] = pending
    else:
        pending = None
    # DSH marks every steered continuation as a report, including a revision;
    # the persisted, explicitly authorized pending chain is more specific.
    recovery_pending = core.pending_recovery(((marker or {}).get('chains') or {}).get(data['prompt_id']))
    report = not recovery_pending and bool(data.get('consolex_report') and not pending or marker and marker.get('review_gate'))
    core.sync_noted_methods(env, data.get('session_id'), data.get('cwd') or os.getcwd(), http=http,
                            skip_task=(marker or {}).get('task_uuid') if marker and not report else None)
    _journal_reply(env, data, report=report)
    if not marker:
        return None
    data['last_assistant_message'] = data.get('last_assistant_message') or ''
    marker['last_assistant_message'] = data['last_assistant_message']
    core.save_marker(env, marker)
    if report:
        core.end_turn(data, env, http=http)
        return None  # One report continuation, never another delivery before a human answer.
    data['stop_hook_active'] = False
    data['tools'] = _records(marker)
    data['tool_notes'] = marker.get('tool_notes', {})
    # Duplicate Stop events reuse the existing idempotency key, including after
    # network uncertainty. A different delivery or a new human turn gets a new attempt.
    digest = hashlib.sha256((data['prompt_id'] + '\0' + data['last_assistant_message']).encode()).hexdigest()
    previous = marker.get('delivery_event') or {}
    if previous.get('digest') == digest and previous.get('completed') and not recovery_pending:
        return {'systemMessage': previous.get('message', 'ConsoleX: already checked.')}
    if previous.get('digest') == digest and not recovery_pending:
        marker['attempts'] = max(0, previous['attempt'] - 1)
    if pending and core.parse_delivery(data['last_assistant_message']):
        # Consume this authorization before checking the revision. A later
        # report-only block must not inherit the preceding revision's flag.
        marker['chains'][pending]['sent_back'] = False
        marker.pop('continuation_chain', None)
    marker['delivery_event'] = {'digest': digest, 'attempt': int(marker.get('attempts') or 0) + 1}
    if runtime == 'deepseek_harness':
        marker.pop('stage_held', None)  # set again by this Stop's stage checks only if they hold the run now
    core.save_marker(env, marker)
    output = core.handle(data, env, http=http)
    marker = core.load_marker(env, data.get('session_id')) or marker
    held = runtime == 'deepseek_harness' and _stage_hold(marker, data['prompt_id'])
    if held:
        # DSH steers one report step for every answer a Stop gives. While stage checks hold the run (paused for the owner,
        # or a single-stage plan waiting), a pending revision cannot go on: suspend it, so that report step's stop ends
        # the turn instead of being taken for the revision again (which would report the hold over and over).
        for key in {pending, data['prompt_id']} - {None}:
            if key in (marker.get('chains') or {}):
                marker['chains'][key]['sent_back'] = False
        marker.pop('continuation_chain', None)
    if output:
        if output.get('decision') == 'block':
            tag = '[ConsoleX continuation %s]' % digest[:16]
            chain = (marker.get('chains') or {}).get(data['prompt_id']) or {}
            if chain.get('sent_back'):
                marker.pop('review_gate', None)
                marker['continuation_chain'] = data['prompt_id']
            else:
                marker['review_gate'] = True
                marker.pop('continuation_chain', None)
            marker['continuation_tag'] = tag
            output['reason'] = tag + '\n' + output['reason']
        # Unreachable submissions are retryable with exactly the same attempt.
        chain = (marker.get('chains') or {}).get(data['prompt_id']) or {}
        # Whether the delivery was checked comes from the result line as the check made it. When a stage report was added
        # to the line (free text from the stages' own requirements), core kept the line it was added to.
        checked_line = marker['result_message'] if 'result_message' in marker else output.get('systemMessage')
        marker['delivery_event']['completed'] = bool(not core.pending_recovery(chain) and checked_line and
            'not checked' not in checked_line.lower() and '没有检查' not in checked_line)
        if pending and not held and not marker['delivery_event']['completed'] and output.get('decision') != 'block':
            marker['chains'][pending]['sent_back'] = True
            marker['continuation_chain'] = pending
        marker['delivery_event']['message'] = core._plain_text(output.get('systemMessage', ''))  # as the owner reads it
        marker.pop('result_message', None)
        core.save_marker(env, marker)
    return adapt(output, runtime)


def _stage_hold(marker, prompt_id):
    """True when this very Stop was answered by the stage checks holding the run, not by a delivery check: the server
    paused it (also a pause remembered while it is unreachable), or a single-stage plan reported its wait. Decided from
    this Stop's own outcome (`stage_held`, dropped before the Stop and set by core.checkpoint_hook), never from an earlier
    report of the same turn: DSH can take the owner's "continue" into that turn after the run went on."""
    return bool(marker and marker.get('checkpoint_required') and marker.get('stage_held') == prompt_id)


@contextlib.contextmanager
def session_lock(env, session_id):
    """Serialize parallel tool hooks and Stop without losing evidence or attempts."""
    path = core._marker_path(env, session_id)
    if not path:
        yield
        return
    with open(path + '.lock', 'a+b') as lock:
        os.utime(path + '.lock')  # In use: keep it out of the week-old sweep.
        if os.name == 'nt':
            import msvcrt
            lock.write(b'0'); lock.flush(); lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def main():
    runtime = os.environ.get('CONSOLEX_RUNTIME', 'codex')
    env = environment(dict(os.environ), runtime)
    try:
        data = json.load(sys.stdin)
        with session_lock(env, data.get('session_id')):
            output = handle(data, env, runtime)
    except Exception as exc:
        output = {'systemMessage': 'ConsoleX: check unavailable (%s); not checked.' % type(exc).__name__}
    if output:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
