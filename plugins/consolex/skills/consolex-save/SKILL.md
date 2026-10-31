---
name: consolex-save
description: Save this Codex session as a ConsoleX task draft (your messages, the final reply and the tool records), optionally with a task name.
---

The ConsoleX UserPromptSubmit hook has already sent this session to ConsoleX as a task draft (or found why it could not) and added the result to context. Tell the user what it says in two or three lines: what was sent and the link to review the draft. Do not run any commands, create files or save anything yourself. If no ConsoleX hook result is present, explain that the ConsoleX hooks must be installed and trusted; do not claim the session was saved.
