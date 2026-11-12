---
name: consolex-save
description: Save this Codex session as a ConsoleX task, optionally with a task name. The method stays in one skill here; ConsoleX keeps the delivery goal, run rules and checks.
---

The ConsoleX UserPromptSubmit hook has prepared this save and added its steps to context (a note that starts with "ConsoleX: the user ran $consolex-save"). Nothing has been sent yet. Follow those steps exactly: choose or create the task's main skill, ask the user once before writing new requirements into an existing skill, then call the ConsoleX tool `consolex_save` with the save id the note gives (if this session has no such tool, run the command the note gives instead), and tell the user in two or three lines what it says, with its review link. Do not send anything to ConsoleX any other way. If the note says ConsoleX is not connected or there is nothing to save, tell the user in one line and do nothing else. If no ConsoleX hook result is present, explain that the ConsoleX hooks must be installed and trusted; do not claim the session was saved.
