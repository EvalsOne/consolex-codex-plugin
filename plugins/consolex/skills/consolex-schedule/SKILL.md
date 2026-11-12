---
name: consolex-schedule
description: Run a ConsoleX task on a schedule as a scheduled task in the Codex app; a task not yet added on this computer is added first. The scheduled prompt only says where to run and which task; what to do, what to publish and what happens after a failed check all come from the task in ConsoleX.
---

The ConsoleX UserPromptSubmit hook has already looked the task up (among the tasks added on this computer, then in ConsoleX, adding it first when it was not there) and added what to do next, with the exact prompts, to context. Follow it: turn the time into an RRULE, then create the scheduled task with the Codex app's automation_update tool (or update the one that already runs this task), passing the prompt exactly as given. If several tasks or none were listed, show the list, ask which task, and create nothing.

If no ConsoleX hook result is present, call the ConsoleX consolex_schedule tool with the task part of the arguments (not the time) and this chat's folder, and follow its result the same way. If you have no such tool either, explain that the ConsoleX hooks must be installed and trusted; create nothing.
