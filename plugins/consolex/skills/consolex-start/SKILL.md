---
name: consolex-start
description: Do a ConsoleX task in this session without adding it as a Skill. Give words from its name or its ConsoleX link, optionally followed by -- and a request for this time.
---

The ConsoleX UserPromptSubmit hook handles this explicit command and adds its result to context. If the task was loaded, say briefly which task you are starting, then do it now by following the task Skill, latest approved method and tools note in that context. Read any listed supporting SKILL.md paths when a step needs them. ConsoleX checks the delivery as for an added task. If several tasks matched, show the candidates and ask the user to run $consolex-start with more words from the chosen name. Otherwise relay the result concisely and do nothing else. If no ConsoleX hook result is present, explain that the ConsoleX hooks must be installed and trusted; do not claim a task was started or invent task instructions.
