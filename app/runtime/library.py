"""Research library: subjects the user wants researched in depth, each with a Markdown report in the workspace
(library/<slug>/report.md) that the agent writes, the user refines in a chat bound to the subject, and every task can
search (library_search; the top hits are handed to the agent at the start of a task, like memory facts).

The report file is the source of truth (the user can read and edit it in the workspace); the FTS index is rebuilt
from it whenever a task bound to the subject finishes or the file is written through files_write.
"""
from __future__ import annotations

import hashlib
import os
import re
import time

from app.common.util import new_id, now_ts

CHUNK_CHARS = 1200
STATUSES = ("researching", "ready", "empty", "failed")


def slugify(title: str) -> str:
    """ASCII slug for the folder name. A title with non-Latin text (Chinese, say) keeps its Latin words plus a short hash of
    the whole title, so "家用 NAS 选购" and "办公 NAS 选购" get different folders."""
    t = (title or "").strip()
    s = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:48]
    if re.search(r"[^\x00-\x7f]", t) or len(s) < 3:
        s = (s or "subject") + "-" + hashlib.sha1(t.encode()).hexdigest()[:8]
    return s


def report_path(slug: str) -> str:
    return f"library/{slug}/report.md"


def chunks(text: str) -> list[tuple[str, str]]:
    """(heading, text) pieces of a Markdown report: a new piece at every heading; within a section, paragraphs (blank-line
    separated) are packed into pieces of at most CHUNK_CHARS; a single longer paragraph is a piece of its own."""
    out: list[tuple[str, str]] = []
    heading = ""
    paras: list[str] = []
    cur: list[str] = []

    def end_para():
        if cur:
            p = "\n".join(cur).strip()
            if p:
                paras.append(p)
            cur.clear()

    def flush():
        end_para()
        piece: list[str] = []
        size = 0
        for para in paras:
            if piece and size + len(para) + 2 > CHUNK_CHARS:
                out.append((heading, "\n\n".join(piece)))
                piece, size = [], 0
            piece.append(para)
            size += len(para) + 2
        if piece:
            out.append((heading, "\n\n".join(piece)))
        paras.clear()
    for line in (text or "").splitlines():
        if re.match(r"^#{1,4}\s+\S", line):
            flush()
            heading = line.lstrip("#").strip()
        elif not line.strip():
            end_para()
        else:
            cur.append(line)
    flush()
    return out


def read_report(workspace: str, slug: str) -> str:
    p = os.path.join(workspace, report_path(slug))
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(2_000_000)
    except OSError:
        return ""


def index_subject(store, workspace: str, subject: dict) -> int:
    """Rebuild the subject's search index from its report; sets status ready / empty. Returns the chunk count."""
    text = read_report(workspace, subject["slug"])
    pieces = chunks(text)
    store.library_replace(subject["id"], pieces)
    store.update_subject(subject["id"], status="ready" if pieces else "empty", chars=len(text))
    return len(pieces)


def research_goal(subject: dict, refresh: bool, language: str = "zh") -> str:
    """The task text that starts (or refreshes) the research of a subject; the deep-research skill does the rest."""
    path = report_path(subject["slug"])
    if language == "en":
        head = (f"RESEARCH SUBJECT: {subject['title']}\nBrief: {subject['brief'] or '(none)'}\n"
                f"Report file: {path} (Markdown; sources go in library/{subject['slug']}/sources.md).\n")
        if refresh:
            return head + ("This is a REFRESH: read the existing report first (files_read), look for what is new or changed since, "
                           "update the affected sections in place and append a dated '## Changelog' entry at the end. "
                           "Call load_skill('deep-research') for the method.")
        return head + ("Research this subject thoroughly and write the report to that file. Call load_skill('deep-research') "
                       "first and follow it.")
    head = (f"研究课题 RESEARCH SUBJECT: {subject['title']}\n要求 Brief: {subject['brief'] or '(无)'}\n"
            f"报告文件 Report file: {path}（Markdown；来源写在 library/{subject['slug']}/sources.md）。\n")
    if refresh:
        return head + ("这是一次刷新 REFRESH：先用 files_read 读现有报告，查找此后的新情况或变化，就地更新受影响的章节，并在末尾追加带日期的"
                       "「## Changelog」条目。先调用 load_skill('deep-research') 按其方法做。")
    return head + "请对这个课题做全面研究，把报告写到该文件。先调用 load_skill('deep-research') 并按其方法做。"


def chat_context(subject: dict, report: str, language: str = "zh") -> str:
    """Executor prompt section for a conversation bound to a subject: the report is the thing being discussed."""
    path = report_path(subject["slug"])
    body = report.strip() or ("(the report is still empty)" if language == "en" else "（报告还是空的）")
    if len(body) > 24_000:
        body = body[:24_000] + "\n…(truncated; files_read the file for the rest)"
    if language == "en":
        return (f"\n## Research subject: {subject['title']}\nThis conversation is about a research subject in the user's library. "
                f"Its report is the file {path}; the current text is below. When the user asks a question, answer from the report "
                f"(and research further with browser_search / browser_read when it lacks the answer). When the user asks for a change, "
                f"addition or correction, edit the report file with files_write (rewrite the affected section; keep the rest), append a "
                f"dated entry to its '## Changelog' section, and tell the user what changed. Keep the report's structure.\n"
                f"### Current report\n{body}\n")
    return (f"\n## 研究课题 Research subject: {subject['title']}\n这个对话围绕用户研究库里的一个课题。报告文件是 {path}，当前内容在下面。"
            f"用户提问时依据报告回答（报告里没有的再用 browser_search / browser_read 查）；用户要求修改、补充或纠正时，用 files_write 改报告文件"
            f"（重写受影响的章节，其余保留），在「## Changelog」末尾追加带日期的条目，并告诉用户改了什么。保持报告结构。\n"
            f"### 当前报告 Current report\n{body}\n")


def hits_context(hits: list[dict], language: str = "en") -> str:
    """Executor prompt section listing the library passages that match this task's request."""
    if not hits:
        return ""
    lines = [f"- [{h['title']}] {h['heading'] + ': ' if h.get('heading') else ''}{h['text'][:500]}" for h in hits]
    if language == "en":
        return ("\n## From your research library\nPassages from reports the user had researched earlier that match this request "
                "(library_search finds more; library_get reads a whole report):\n" + "\n".join(lines) + "\n")
    return ("\n## 来自研究库 From the research library\n用户之前研究过的报告里与本请求相关的段落（library_search 可查更多，library_get 读整份报告）：\n"
            + "\n".join(lines) + "\n")


def new_subject(title: str, brief: str) -> dict:
    return {"id": new_id("subj"), "slug": slugify(title), "title": (title or "").strip()[:120], "brief": (brief or "").strip()[:4000],
            "status": "researching", "conv_id": "", "created_at": now_ts(), "updated_at": now_ts(), "last_task": "", "runs": 0,
            "chars": 0, "error": ""}
