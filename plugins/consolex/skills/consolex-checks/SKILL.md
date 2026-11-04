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
- When the user asks in plain words for login, status, their task list, adding or removing a task, or an isolated run's command, call the ConsoleX tool `consolex_command` with that command and the words that follow it; the result is the same as the typed command. When they want a ConsoleX task to run by itself at set times (or to change, pause or stop that), call `consolex_schedule` with the task and this chat's folder, and follow its result: it gives the exact prompt for the Codex app's automation_update tool. Never write a scheduled prompt yourself. Logout and save stay the user's own commands: never run them for the user.
- `$consolex-run <task>` shows the terminal command of an isolated run: a new Codex session in its own folder with only the task's Skills, files and ConsoleX tools (ConsoleX runs and bills each tool call). Only the user starts it.
- `$consolex-save [task name]` sends the current session (the user's messages, the final reply and the tool records, keys masked) to ConsoleX as a task draft; the user reviews and saves it there, and this result becomes the task's first run. Only the user runs it; never suggest it in place of finishing the work, and never send anything to ConsoleX yourself.
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
- Deliverable: this reply        (or one "- File: relative/path" line per text file you wrote)
```

Write the confirmation section once in the whole reply. Many task methods already ask for a 「待你确认」 / "Needs your confirmation" section: then that is the one, so do not add a second copy.

Write each decision as a choice with its options ("Register cairninbox.com alone, or with .ai and .io too?"), so it can be put to the owner as a question.

Leave both sections out while you are asking a question or reporting progress: only a reply with the delivery section is checked. The judge also sees the tool calls and results of this session, so check facts with real tools (lookups, fetches, searches) rather than stating them; printing a result yourself (for example with echo) is not evidence. For file deliverables, list only text files you wrote or changed for this task, with paths relative to the current folder.

## After the check

ConsoleX checks the delivery against the task's saved standard with the checking model recorded in the result (ConsoleX reports whether cross-family independence is confirmed). When it passes and nothing needs confirmation, the plugin only shows the result.

When it passes (or could not be checked) and the delivery lists items under "Needs your confirmation", the turn continues once with a ConsoleX message that starts with the result. Then, without changing the deliverable or delivering again, give the owner the result in one line with the run link and ask about the items: with request_user_input when you have it (one question per item that needs a decision, at most 4, each with 2-4 concrete options from the delivery; mention reminders in your message), otherwise as questions in text, and stop. Act on the owner's answers; if they change the deliverable, deliver again with the delivery section.

When a check fails or needs the owner's review, the turn continues once with a ConsoleX message listing the items and reasons. Then:

1. Do not change the deliverable and do not deliver again yet.
2. Tell the owner the result in one short message: each item with its reason, and the run link.
3. Ask whether to revise for these items: with request_user_input when you have it (options "Revise these items" / "Keep as is"; items to confirm go into the same call as further questions), otherwise in one line, and stop.
4. Only after the owner says to revise: fix those items in the deliverable itself and deliver again with the delivery section. ConsoleX checks it again and the owner decides again.

Never invent facts, sources or approvals to pass a check, and do not add content only because a check named it; if a failed item asks for something the method never mentioned, say so to the owner. If an item needs the owner's decision or information you do not have, put it under "Needs your confirmation". A delivery made without the owner's go-ahead is not checked.

- `$consolex-check` checks the latest reply now; `$consolex-check off` stops checking this session.
- Every checked attempt appears in the task's run history in ConsoleX, labelled "External · Codex".
