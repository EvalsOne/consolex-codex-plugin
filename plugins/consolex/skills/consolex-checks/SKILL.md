---
name: consolex-checks
description: How ConsoleX tasks work in Codex - connecting, adding tasks, saving a session as a task, and how deliveries are checked. Use when a ConsoleX task Skill (a cx-… Skill) is active, when ConsoleX reports a check result, or when the user asks how to use ConsoleX in Codex.
---

# ConsoleX in Codex

## Setting up (the user does this, once per computer)

- `$consolex-login` connects this computer: the browser opens, the user approves the code in ConsoleX, and the plugin saves the connection by itself. A development or self-hosted ConsoleX takes its API address: `$consolex-login https://…`.
- `$consolex-status` shows this computer's connection, account, device, permission for tools and files, added tasks and current task, as reported by ConsoleX.
- `$consolex-start <task> [-- request]` does a task here without adding a Skill: follow the task body and latest approved method in context, and read supporting SKILL.md paths when needed. Its delivery is checked as usual. Multiple matches require the user to choose.
- `$consolex-tasks` lists the user's ConsoleX tasks; `$consolex-add <words from a task name>` (or a ConsoleX task link) adds one as a `$cx-…` Skill. `$consolex-remove <task>` takes an added task off this computer (the task stays in ConsoleX). `$consolex-schedule <task> <when>` runs an added task on a schedule in the Codex app. `$consolex-logout` disconnects the computer.
- When the user asks in plain words for login, status, their task list, adding or removing a task, call the ConsoleX tool `consolex_command` with that command and the words that follow it; the result is the same as the typed command. When they want a ConsoleX task to run by itself at set times (or to change, pause or stop that), call `consolex_schedule` with the task and this chat's folder, and follow its result: it gives the exact prompt for the Codex app's automation_update tool. Never write a scheduled prompt yourself. Logout and save stay the user's own commands: never run them for the user.
- `$consolex-save [task name]` sends the current session to ConsoleX as a task: the method stays in one skill on this computer (the task's main skill, which the plugin's note has you choose or create and bring up to date, asking the user once before you add requirements to an existing skill), and ConsoleX keeps the delivery goal, run rules and checks. You then call `consolex_save` with the note's save id (in a session without that tool, the command the note gives); the user reviews and saves the draft in ConsoleX. Saving alone does not create or check a first run: the user must explicitly choose to check the selected result preview. The plugin then adds the saved task here as a $cx-… Skill by itself. When a task's method is a skill, load that skill and follow it; if it is not on this computer, stop and tell the user (the plugin records that the run did not happen). Only the user starts it; never suggest it in place of finishing the work, and never send anything to ConsoleX any other way.
- When `$consolex-add` asks you to give a task an English Skill name, translate what it makes into 2 to 4 words, call `consolex_rename_skill`, then report the resulting `$cx-…` name. Use the installed name if renaming fails. Later updates keep the chosen name.
- These commands are handled by the plugin. Never edit `~/.consolex/credentials.json`, never ask the user for a token, and never create task Skills by hand.

## Working on a task

A ConsoleX task Skill (`cx-…`) carries one task's method and an output contract. When it loads, the plugin marks the session and adds the latest approved method to your context; follow that method.

You do not see the task's acceptance standard: it stays in ConsoleX so the check is independent of you. Do the work the method describes as well as you can; do not guess at or write to hidden checks. After a check you see only the items that did not pass, with their reasons.

When you hand over the result, end your reply with the two sections the output contract names, the delivery section last:

```
## Needs your confirmation      (or: ## 待你确认)
- Anything the owner must decide or verify; "None" if nothing
## ConsoleX delivery            (or: ## ConsoleX 交付)
- Deliverable: this reply        (or one "- File: path/from/the/project/folder" line per text file you wrote)
```

Write the confirmation section once in the whole reply. Many task methods already ask for a 「待你确认」 / "Needs your confirmation" section: then that is the one, so do not add a second copy.

Write each decision as a choice with its options ("Register cairninbox.com alone, or with .ai and .io too?"), so it can be put to the owner as a question.

Leave both sections out while you are asking a question or reporting progress: only a reply with the delivery section is checked. The judge also sees the tool calls and results of this session, so check facts with real tools (lookups, fetches, searches) rather than stating them; printing a result yourself (for example with echo) is not evidence. For file deliverables, list only text files you wrote or changed for this task, with paths relative to the project folder (or absolute paths), even after changing folder. Plain paths, inline-code paths and Markdown links to local files are accepted. Supported UTF-8 formats include .md, .txt, .json, .jsonl, .csv and .html; each file must fit the 200 KB limit. An unreadable declared file prevents submission, so do not silently omit required evidence.

## Tasks done in stages (reminder mode)

Some tasks are handed in stage by stage. The ConsoleX note at the start then lists the stages, what each needs, and an execution id. Nothing pauses in this mode and nobody has to be waited for.

- When you finish a stage, call `consolex_checkpoint` with the task, the execution id, `operation` "submit", the `stage_key` and the COMPLETE text of that stage's deliverable (never a summary or a path). The reply is that stage's check result: a pass, or the requirements that were not met.
- Fix what did not pass and hand the stage in again before you start the next one. A stage that still does not pass is shown to the owner; carry on and say so in your reply, and neither stop nor wait. A "checking" result means the check is still running: carry on, its result is recorded. `consolex_checkpoint` with `operation` "status" shows where the stages stand.
- Pass the execution id on every ConsoleX tool call: `execution_id` to `consolex_run_task_tool`, `consolex_execution_id` to a tool of a task-bound ConsoleX server. A tool that is not tied to a stage runs as usual. An action tied to a stage (such as speech generation) is held with "Not yet" until its stage has passed with exactly that text: hand the stage in, then call it again with the identical text. A hold is not an error and not a reason to stop. Never get around it with a shell command, the browser, direct HTTP or another MCP server.
- When ConsoleX says the run is paused for the owner (for example after a speech call whose result is unknown, which must never be repeated), make no more ConsoleX tool calls, give the owner the review link and stop. The owner decides in ConsoleX and then tells you to continue in this same chat; ConsoleX does not wake a stopped session.
- The stages that did not pass are reported to the owner when your turn ends. Ending your turn is never held back for them, and the final delivery is checked as usual.

## After the check

ConsoleX checks the delivery against the task's saved standard with the checking model recorded in the result (ConsoleX reports whether cross-family independence is confirmed). When it passes and nothing needs confirmation, the plugin only shows the result.

When it passes (or could not be checked) and the delivery lists items under "Needs your confirmation", the turn continues once with a ConsoleX message that starts with the result. Then, without changing the deliverable or delivering again, give the owner the result in one line with the run link and ask about the items: with request_user_input when you have it (one question per item that needs a decision, at most 4, each with 2-4 concrete options from the delivery; mention reminders in your message), otherwise as questions in text, and stop. Act on the owner's answers; if they change the deliverable, deliver again with the delivery section.

Iteration is off by default for new tasks; existing tasks keep their saved setting. The owner can enable 1–10 revisions. Each revision and AI check has its usual charge. The plugin's current ConsoleX message tells you whether another revision is authorized; do not infer authorization from a failed verdict alone.

When that message says the owner enabled iteration and asks you to revise, fix the listed output items without asking again, preserve the parts that already meet the requirements, and deliver the full result again with the delivery section. Required output failures from rules and AI checks share this loop and its saved limit. Follow each new check result; stop when the plugin reports a final result or tells you to stop. Host limits may end the loop before the saved limit. If an older server explicitly sends a rules-only revision instruction, follow that narrower scope.

Unknown results, missing external evidence and items needing the owner's decision are not permission to keep rewriting. Do not change the acceptance criteria or perform unauthorized external actions to pass. Put unresolved decisions under "Needs your confirmation".

Evidence recovery is a separate, default-off task setting. The plugin may add relevant, already captured excerpts and recheck once while keeping the original evidence and standard. Do not run new tools or rewrite the delivery just to recover evidence. If it reports an uncertain recheck, `$consolex-check` resumes that same attempt; do not start another task or submit a new delivery to retrieve its result. Unchanged evidence reuses the original check without a new check charge.

When the plugin reports failed items or asks for the owner's review without authorizing another revision (including when iteration is off or has stopped):

1. Do not change the deliverable and do not deliver again yet.
2. Tell the owner the result in one short message: each item with its reason, and the run link.
3. Ask whether to revise for these items: with request_user_input when you have it (options "Revise these items" / "Keep as is"; items to confirm go into the same call as further questions), otherwise in one line, and stop.
4. After the owner says to revise, fix those items in the deliverable itself and deliver again with the delivery section. ConsoleX checks it again; follow its next instruction.

In an unattended run (a scheduled task or an isolated headless run), follow authorized revision instructions as above, but never ask questions or wait for an answer. Leave open decisions under "Needs your confirmation". When the plugin reports the final result without authorizing another revision, summarize the result and run link and stop.

Never invent facts, sources or approvals to pass a check, and do not add content only because a check named it; if a failed item asks for something the method never mentioned, say so to the owner. Do not submit another attempt after a report-only result until the owner authorizes it.

- `$consolex-check` checks the latest reply now; `$consolex-check off` stops checking this session.
- Every checked attempt appears in the task's run history in ConsoleX, labelled "External · Codex".
