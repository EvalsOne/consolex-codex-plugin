# ConsoleX for Codex

Do your [ConsoleX](https://consolex.ai) tasks in Codex and have every delivery checked against the task's saved acceptance standard before Codex finishes.

A ConsoleX task holds a method (how to do the work) and an acceptance standard (what a good result must meet). This integration adds a task to Codex as a `$cx-…` Skill. When Codex hands over the result, ConsoleX checks it with an independent judge and records the attempt in the task's run history. Codex never sees the acceptance standard, only the method, so the check stays independent. When a check fails or needs review, Codex sees just those items, tells you, and changes nothing until you say so.

## Requirements

- Codex CLI. Tested with 0.162.1.
- `python3` (3.9 or later). The integration uses only the Python standard library; nothing is installed or downloaded.
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

| Command | What it does |
| --- | --- |
| `$consolex-login` | Connects this computer once. Your browser opens; approve the code in ConsoleX. |
| `$consolex-tasks [words]` | Lists your ConsoleX tasks and whether each is installed here. |
| `$consolex-add <words from a task name or a task link>` | Installs the task as a `$cx-…` Skill, with the ConsoleX Skills it uses. Run it again to update. |
| `$cx-<task name>` | Starts the task. |
| `$consolex-check [off]` | Checks the current task's latest delivery now; `off` turns checks off for this session. |
| `$consolex-save [task name]` | Sends this session to ConsoleX as a task draft that you review and save there. |
| `$consolex-run <task>` | Prints the terminal command for an isolated run of the task (a new Codex session with only the task's Skills, files and ConsoleX tools). |
| `$consolex-logout` | Disconnects this computer. You can also remove computers in ConsoleX under Settings › Coding agents. |

## What the installer changes

- Copies the integration to `~/.consolex/codex-integration`.
- Adds the ConsoleX hooks to `~/.codex/hooks.json` (`SessionStart`, `UserPromptSubmit`, `PreToolUse` on `request_user_input`, `PostToolUse`, `Stop`, `SessionEnd`, `Interrupt`). Your other hooks are kept, and the file is first backed up to `hooks.before-consolex.json`. Hooks are never trusted for you.
- Adds a marked block to `~/.codex/config.toml` that registers the MCP server `consolex` (backed up first to `config.before-consolex.toml`). It is pre-approved because Codex refuses, without asking, an MCP call that needs approval under Full access; your consent is the computer's "Tools and files" permission in ConsoleX. It refuses to install if `config.toml` already defines an MCP server named `consolex`.
- Installs the `consolex-…` command Skills in `~/.agents/skills`. It never replaces a Skill it did not install.

`--codex-home`, `--skills-dir` and `--data-dir` change these locations.

## What the integration runs, stores and sends

Everything runs locally with your user permissions.

**Where it connects.**

- The ConsoleX API, `https://api.consolex.ai`, or the address you pass to `$consolex-login` or set in `CONSOLEX_API_BASE`. A connection or task Skill saved with `https://api.evalsone.com`, the former address of the same API, is sent to `https://api.consolex.ai`.
- Amazon S3, only in an isolated run: the task's own files are downloaded from 10-minute links that ConsoleX issues on its S3 storage (`amazonaws.com` addresses), at most 50 files of up to 50 MB each.
- `$consolex-login` opens the ConsoleX approval page on `consolex.ai` in your browser. The integration itself does not call that site.

**Hooks.** When you start a `$cx-…` task, the hooks mark the session, fetch the task's latest approved method and tell ConsoleX a session started. While that session works they collect its tool calls, tell ConsoleX when a question to you is open, submit a reply that has a "ConsoleX delivery" section for checking, and show the result. In any other session they exit without a network call, except a background refresh of your installed task Skills at session start, at most once an hour.

**MCP server.** `consolex` gives Codex two tools, `consolex_task_tools` and `consolex_run_task_tool`, to call the tools of your ConsoleX tasks. ConsoleX runs each call with your connections, records it and bills it like a run in ConsoleX. This needs the "Tools and files" permission for the computer in ConsoleX.

**Isolated runs.** `$consolex-run` only prints a command. When you run that command (`~/.consolex/bin/consolex-codex run '<task>'`) in a terminal, it creates `~/ConsoleX/<task>/` with the task's Skills and files, and starts Codex there with its own Codex home (your Codex sign-in linked, ConsoleX hooks trusted, only the ConsoleX MCP server) and an empty home folder, so none of your own Skills, plugins, MCP servers, memories or `AGENTS.md` load. It changes nothing in your own Codex settings.

**Stored on your computer.**

- `~/.consolex/credentials.json` (mode 0600): the device token from `$consolex-login`. Remove it with `$consolex-logout`.
- `~/.consolex/codex-integration`: the installed integration. `~/.consolex/bin/consolex-codex`: the isolated-run launcher.
- `~/.agents/skills/cx-…`: task Skills you add, and the ConsoleX Skills they use. Task Skills hold no secrets.
- `~/.consolex/codex/sessions`: session state, kept for 7 days. `~/.consolex/codex-isolated/` and `~/ConsoleX/<task>/`: isolated runs, only when you run one.

**Sent to ConsoleX with a delivery.** The delivery (the reply, or the text files it names), the "Needs your confirmation" items, the model id, and the tool calls of this session since the task started: commands, URLs, queries and file paths with their results. Long outputs are shortened, images are not sent, and keys and tokens are masked. Only the latest 80 tool calls are sent, so use one session per task. Set `CONSOLEX_TOOL_EVIDENCE=off` to send only the delivery.

**Fetched from ConsoleX.** Your task list, a task's method and the Skills it uses, and check results.

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
