# ConsoleX for Codex

Do your [ConsoleX](https://consolex.ai) tasks in Codex and have every delivery checked against the task's saved acceptance standard before Codex finishes.

A ConsoleX task holds a method (how to do the work) and an acceptance standard (what a good result must meet). This integration adds a task to Codex as a `$cx-…` Skill. When Codex hands over the result, ConsoleX checks it against the saved standard when automatic checks are enabled and records the attempt in the task's run history. Codex never sees the acceptance standard, only the method. The checker uses a different model family when available, and discloses when it is not independent. When a check fails or needs review, Codex reports the items for your decision; optional automatic revision can retry failed required output checks.

## Requirements

- Codex CLI.
- Git and `python3` (3.9 or later). The integration uses only the Python standard library.
- A ConsoleX account on a paid plan to connect a computer.
- Network access to `*.consolex.ai`: the integration calls the API at `api.consolex.ai`, and tasks and Skills can link to files on `static.consolex.ai`, ConsoleX's file CDN.

## Install

```bash
git clone https://github.com/EvalsOne/consolex-codex-plugin.git
python3 consolex-codex-plugin/install.py
```

Restart Codex, open `/hooks`, review and trust **ConsoleX delivery checks**, then run `$consolex-login`.

The installer copies what it needs to `~/.consolex/codex-integration`, so you can delete the clone afterwards. To update, pull (or clone again), run `install.py` again and re-trust the changed hooks in `/hooks`.

Why an installer: Codex CLI 0.162.1 loads plugin Skills but does not run a plugin's hooks, and ConsoleX does its work in hooks. The repository is also a Codex plugin marketplace (`.agents/plugins/marketplace.json`) for hosts that run plugin hooks, but installing from the marketplace alone does nothing on that CLI.

To remove it: `python3 install.py --uninstall` (from a clone of this repository). It removes only what the installer added and keeps your ConsoleX sign-in, which other coding agents on this computer may share.

## Use

You can type these commands, or ask Codex in plain words ("add 小语评球 to this computer", "run 小语评球 every weekday at 8:30") and it runs login, status, tasks, add, remove, schedule or run for you through the ConsoleX tools `consolex_command` and `consolex_schedule`, with the same result. `$consolex-save` and `$consolex-logout` you type yourself.

| Command | What it does |
| --- | --- |
| `$consolex-login` | Connects this computer once. Your browser opens; approve the code in ConsoleX. |
| `$consolex-status` | Shows this computer's connection, account, device, tools/files permission, added tasks and active task. |
| `$consolex-add <words from a task name or a task link>` | Installs the task as a `$cx-…` Skill, with the ConsoleX Skills it uses. Run it again to update. With no words, it lists your ConsoleX tasks and whether each is added here (`$consolex-tasks [words]` searches the list without adding anything). |
| `$consolex-remove <task>` | Takes an added task off this computer only: its `$cx-…` Skill and the ConsoleX Skills installed only for it. The task stays in ConsoleX. |
| `$consolex-schedule <task> <when>` | Runs an added task on a schedule as a scheduled task in the Codex app ("小语评球 every weekday at 8:30"). Codex sets it up with a fixed prompt that only names the folder and the task; what to do and what to publish come from the task in ConsoleX. A task runs from one place: while it has a schedule in ConsoleX or on another computer, nothing is set up here. The Codex app must be open on this computer at that time. |
| `$consolex-start <task> [-- request]` | Does a task in this session without adding it as a Skill; the delivery is checked as usual. Give words from its name or its ConsoleX link. |
| `$cx-<task name>` | Starts the task. |
| `$consolex-check [off]` | Checks the current task's latest delivery now; `off` turns checks off for this session. |
| `$consolex-save [task name]` | Sends this session to ConsoleX as a task draft that you review and save there. Type it yourself. |
| `$consolex-logout [api address \| all]` | Disconnects this computer. Type it yourself. If this computer is connected to more than one ConsoleX address, it lists them and disconnects nothing until you name one or `all`. If ConsoleX cannot be reached the connection is kept so you can retry; add `--local` to forget it on this computer only. You can also remove computers in ConsoleX under Settings › Coding agents. |

Advanced:

| Command | What it does |
| --- | --- |

When adding a task whose name cannot form a readable Skill name (for example, a Chinese name), Codex gives it a short English Skill name through `consolex_rename_skill`. Later updates keep that name.

## What the installer changes

- Copies the integration to `~/.consolex/codex-integration`.
- Adds the ConsoleX hooks to `~/.codex/hooks.json` (`SessionStart`, `UserPromptSubmit`, `PreToolUse` on `request_user_input` and the tools of the `consolex` MCP server, `PostToolUse`, `Stop`, `SessionEnd`, `Interrupt`). Your other hooks are kept, and the file is first backed up to `hooks.before-consolex.json`. Hooks are never trusted for you.
- Adds a marked block to `~/.codex/config.toml` that registers the MCP server `consolex` (backed up first to `config.before-consolex.toml`). It is pre-approved because Codex refuses, without asking, an MCP call that needs approval under Full access; your consent is the computer's "Tools and files" permission in ConsoleX. It refuses to install if `config.toml` already defines an MCP server named `consolex`.
- Installs the `consolex-…` command Skills in `~/.agents/skills`. It never replaces a Skill it did not install.

`--codex-home`, `--skills-dir` and `--data-dir` change these locations.

## What the integration runs, stores and sends

Everything runs locally with your user permissions.

**Where it connects.**

- The ConsoleX API, `https://api.consolex.ai`, or the address you pass to `$consolex-login` or set in `CONSOLEX_API_BASE`. A connection or task Skill saved with `https://api.evalsone.com`, the former address of the same API, is sent to `https://api.consolex.ai`.
- Amazon S3, only in an isolated run: the task's own files are downloaded from 10-minute links that ConsoleX issues on its S3 storage (`amazonaws.com` addresses), at most 50 files of up to 50 MB each.
- `$consolex-login` opens the ConsoleX approval page on `consolex.ai` in your browser. The integration itself does not call that site.

**Hooks.** When you start a task with `$cx-…` or `$consolex-start`, the hooks mark the session, fetch the task's latest approved method and tell ConsoleX a session started. While that session works they collect its tool calls, tell ConsoleX when a question to you is open, submit a reply that has a "ConsoleX delivery" section for checking, and show the result. In any other session they exit without a network call, except a background refresh of your installed task Skills at session start, at most once an hour.

**MCP server.** `consolex` gives Codex `consolex_task_tools` and `consolex_run_task_tool` to call the tools of your ConsoleX tasks. ConsoleX runs each call with your connections, records it and bills it like a run in ConsoleX. For a task whose method is stored in ConsoleX, this needs the task’s coding-agent tool permission in its run panel.

`consolex_rename_skill` renames an added task Skill locally. `consolex_command` runs login, status, tasks, add, remove or run when you ask for one in plain words; it never logs out or saves a session.

**Isolated runs.** No command offers an isolated run while ConsoleX validates the product. When you run `~/.consolex/bin/consolex-codex run '<task>'` in a terminal, it creates `~/ConsoleX/<task>/` with the task's Skills and files, and starts Codex there with its own Codex home (your Codex sign-in linked, ConsoleX hooks trusted, only the ConsoleX MCP server) and an empty home folder, so none of your own Skills, plugins, MCP servers, memories or `AGENTS.md` load. It changes nothing in your own Codex settings.

**Stored on your computer.**

- `~/.consolex/credentials.json` (mode 0600): the device token from `$consolex-login`. Remove it with `$consolex-logout`.
- `~/.consolex/codex-integration`: the installed integration. `~/.consolex/bin/consolex-codex`: the isolated-run launcher.
- `~/.agents/skills/cx-…`: task Skills you add, and the ConsoleX Skills they use. Task Skills hold no secrets.
- `~/.consolex/started/`: tasks started without adding them, and their supporting Skills. Codex reads these by path.
- `~/.consolex/codex/sessions`: session state, kept for 7 days. `~/.consolex/codex-isolated/` and `~/ConsoleX/<task>/`: isolated runs, only when you run one.

**Sent to ConsoleX with a delivery.** The delivery (the reply, or the text files it names), the "Needs your confirmation" items, the model id, and the tool calls of this session since the task started: commands, URLs, queries and file paths with their results. Long outputs are shortened, images are not sent, and keys and tokens are masked. Only the latest 80 tool calls are sent, so use one session per task. Set `CONSOLEX_TOOL_EVIDENCE=off` to send only the delivery.

**Fetched from ConsoleX.** Your task list, a task's method and the Skills it uses, the connection reported by ConsoleX (`$consolex-status`), and check results.

**Sent at `$consolex-login`.** The computer's name, so you can tell computers apart on the approval page and in Settings.

**Sent with `$consolex-save`.** Your messages in the session, the final reply, the model id and the tool records (keys masked). Nothing is sent unless you run the command.

## Settings

| Variable | Effect |
| --- | --- |
| `CONSOLEX_TOOL_EVIDENCE=off` | Send only the delivery, not the session's tool calls. |
| `CONSOLEX_NO_BROWSER=1` | `$consolex-login` prints the link instead of opening the browser. |
| `CONSOLEX_HOME` | Folder for the connection (default `~/.consolex`). |
| `CONSOLEX_SKILLS_DIR` | Where `$consolex-add` installs Skills (default `~/.agents/skills`). |
| `CONSOLEX_RUNS_DIR` | Where isolated runs are created (default `~/ConsoleX`). |
| `CONSOLEX_TOKEN` | A ConsoleX device token to use instead of the saved connection. It is sent only to the ConsoleX API. |
| `CONSOLEX_API_BASE`, `CONSOLEX_APP_BASE` | A self-hosted or development ConsoleX. |

## Limits

- Deliverables are text: the reply, or UTF-8 text files changed since the task started.
- Only tool calls that reach Codex's `PostToolUse` hook count as evidence; hosted tools, subagent steps and images are not captured. Checks that need more come back as "needs review".

## Privacy and support

- Privacy policy: https://consolex.ai/legal/privacy
- Terms: https://consolex.ai/legal/terms
- Issues: https://github.com/EvalsOne/consolex-codex-plugin/issues

## License

MIT. See [LICENSE](LICENSE).

## Stage checks

Staged checks are an optional preview available only to enabled accounts with a paid plan. When a task has stages enabled, Codex submits intermediate text and reads each verdict; a stage that does not pass is reported and the task continues. Stage checks for new runs do not block tool calls. The former speech-generation gate is paused for new runs; runs already admitted under it keep their original behavior. Final delivery checks remain separate.
