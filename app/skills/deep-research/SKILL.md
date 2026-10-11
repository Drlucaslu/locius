---
name: deep-research
description: 深度研究一个课题并写成可持续更新的报告（研究库）Research a subject in depth and write a report into the library (library/<slug>/report.md); also how to refresh and revise it.
---
# Deep research / 深度研究（研究库 Library）

A subject = a title, a brief (what the user wants to know and why) and a Markdown report the user keeps. Every task bound
to a subject ends with the report file written; the library index is rebuilt from the file automatically.

1. **Plan the questions.** From the brief, list 3–7 sub-questions that together answer it (definitions, options, numbers,
   recent changes, risks, what others recommend). Write them into the plan with update_plan.
2. **Fan out.** For each sub-question use browser_search once, then browser_read the 2–4 best URLs in ONE call. When a
   sub-question needs several pages of digging, delegate(role="researcher", task="<the sub-question + what to return>")
   — up to 5 sub-agents per task, run them for independent questions; keep the easy questions for yourself.
3. **Write as you go.** Context gets compressed: after each sub-question, append its section to the report with
   files_write(path=<report file>, append=true). First call writes the frame:
   `# <title>` · `_Brief: …_` · `## Summary` (fill at the end) · one `## <sub-question>` per finding · `## Open questions` ·
   `## Sources` · `## Changelog`. Facts carry their source and the date checked: "(source: <site>, 2026-10-10)".
   Numbers you did not read on a page are not facts — write "not found" instead of guessing.
4. **Finish.** Rewrite the Summary (files_read the file, then files_write the whole file once) so it answers the brief
   in 5–10 lines; list every URL used under Sources (also in library/<slug>/sources.md, one per line); add
   `## Changelog` → `- <date>: initial research`. The final answer to the user is the Summary plus "report saved to <path>".
5. **Refresh** (the task says REFRESH): files_read the report; search only for what may have changed (news, prices,
   versions, dates); update the affected sections in place; append `- <date>: <what changed>` to the Changelog; say
   "no changes" when nothing moved.
6. **Chat edits** (the user asks a question or wants a section changed in the subject's conversation): answer from the
   report; for a change, files_write the file with the section rewritten and a Changelog line; tell the user what changed.
7. Never put the user's private data (names, addresses, card numbers) into a report; reports are about the subject.
