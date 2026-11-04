---
name: consolex-remove
description: Remove an added ConsoleX task from this computer only (its task Skill and the ConsoleX Skills installed only for it); the task stays in ConsoleX. Not for stopping a scheduled run.
---

The ConsoleX UserPromptSubmit hook has already looked the task up among the tasks added on this computer, removed it when exactly one matched, and added the result to context. Relay that result in one or two lines. If several tasks or none matched, show the list and ask which one. Do not delete files yourself. If no ConsoleX hook result is present, explain that the ConsoleX hooks must be installed and trusted; do not claim the task was removed.
