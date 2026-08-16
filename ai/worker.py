#!/usr/bin/env python3
"""Book Factory worker.

    python3 ai/worker.py --loop              # daemon: keep polling the queue
    python3 ai/worker.py --once              # take one queued book, then exit
    python3 ai/worker.py --once --book-id 7  # build one specific book

PHP fires the third form after you submit the order form (AUTO_SPAWN_WORKER=1),
so nothing has to be running for the site to work. Run --loop instead if you'd
rather have a press sitting idle and ready.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bfconfig import connect, storage_dir  # noqa: E402
from gemini import GeminiError, GeminiWriter  # noqa: E402
from pdf import build_pdf  # noqa: E402

POLL_SECONDS = 3


# ---------------------------------------------------------------------------
# Job log + status
# ---------------------------------------------------------------------------

def log(conn, book_id: int, message: str, level: str = "info") -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO job_events (book_id, level, message) VALUES (%s, %s, %s)",
            (book_id, level, message[:500]),
        )
    print(f"[book {book_id}] {level}: {message}", flush=True)


def set_status(
    conn,
    book_id: int,
    status: str | None = None,
    progress: int | None = None,
    note: str | None = None,
) -> None:
    sets, params = [], []
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if progress is not None:
        sets.append("progress = %s")
        params.append(max(0, min(100, progress)))
    if note is not None:
        sets.append("stage_note = %s")
        params.append(note[:255])
    if not sets:
        return
    params.append(book_id)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE books SET {', '.join(sets)} WHERE id = %s", params)


def fail(conn, book_id: int, message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE books SET status = 'failed', error_message = %s, "
            "stage_note = 'Stopped', finished_at = NOW() WHERE id = %s",
            (message[:2000], book_id),
        )
    log(conn, book_id, message, "error")


# ---------------------------------------------------------------------------
# Claiming work
# ---------------------------------------------------------------------------

def claim(conn, book_id: int | None = None) -> dict[str, Any] | None:
    """Atomically take a queued book. Two workers can't grab the same one."""
    token = secrets.token_hex(16)

    with conn.cursor() as cur:
        if book_id is not None:
            cur.execute(
                "UPDATE books SET status = 'researching', worker_token = %s, "
                "started_at = NOW(), stage_note = 'Reading up on the subject' "
                "WHERE id = %s AND status = 'queued'",
                (token, book_id),
            )
        else:
            cur.execute(
                "UPDATE books SET status = 'researching', worker_token = %s, "
                "started_at = NOW(), stage_note = 'Reading up on the subject' "
                "WHERE status = 'queued' ORDER BY id LIMIT 1",
                (token,),
            )
        if cur.rowcount == 0:
            return None

    with conn.cursor(dictionary=True) as cur:
        cur.execute("SELECT * FROM books WHERE worker_token = %s LIMIT 1", (token,))
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Content cleanup
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    """Strip markdown leftovers and collapse whitespace."""
    text = re.sub(r"\*\*|__|\*|`", "", text)
    text = re.sub(r"^\s*(?:Q|A|Question|Answer)\s*[:.\-]\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*\d+[.)]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def dedupe_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())[:80]


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------

def build_book(conn, book: dict[str, Any]) -> None:
    book_id = int(book["id"])
    chapter_count = int(book["chapter_count"])
    per_chapter = int(book["pages_per_chapter"]) * int(book["questions_per_page"])

    writer = GeminiWriter()
    log(conn, book_id, f"Using {writer.model}.")

    # -- 1. Research -------------------------------------------------------
    set_status(conn, book_id, "researching", 4, "Reading up on the subject")
    log(conn, book_id, f"Researching “{book['theme_label']}”.")

    research = writer.research_theme(
        theme=str(book["theme_label"]),
        title=str(book["title"]),
        chapter_count=chapter_count,
        difficulty=str(book["difficulty"]),
    )
    brief = str(research.get("summary", "")).strip()
    plan = research["chapters"]

    with conn.cursor() as cur:
        cur.execute("UPDATE books SET research_brief = %s WHERE id = %s", (brief, book_id))

    log(conn, book_id, f"Chapter plan ready: {len(plan)} chapters.")

    # -- 2. Chapters -------------------------------------------------------
    set_status(conn, book_id, "writing", 10, "Writing questions")

    chapter_rows: list[dict[str, Any]] = []
    all_questions: list[dict[str, Any]] = []
    used_q: list[str] = []
    used_a: list[str] = []
    seen_q: set[str] = set()
    seen_a: set[str] = set()
    global_no = 0

    for index, planned in enumerate(plan, start=1):
        title = normalise(str(planned.get("title", f"Chapter {index}")))[:200] or f"Chapter {index}"
        angle = str(planned.get("angle", ""))

        set_status(
            conn,
            book_id,
            progress=10 + int(80 * (index - 1) / max(1, chapter_count)),
            note=f"Chapter {index} of {chapter_count}: {title}",
        )

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chapters (book_id, chapter_no, title, intro, is_answer_key) "
                "VALUES (%s, %s, %s, %s, 0)",
                (book_id, index, title, angle),
            )
            chapter_id = cur.lastrowid

        chapter_rows.append(
            {"id": chapter_id, "chapter_no": index, "title": title, "is_answer_key": False}
        )

        accepted: list[dict[str, str]] = []
        attempts = 0

        while len(accepted) < per_chapter and attempts < 3:
            attempts += 1
            shortfall = per_chapter - len(accepted)
            batch = writer.write_chapter(
                theme=str(book["theme_label"]),
                book_title=str(book["title"]),
                difficulty=str(book["difficulty"]),
                brief=brief,
                chapter_no=index,
                chapter_total=chapter_count,
                chapter_title=title,
                chapter_angle=angle,
                count=shortfall,
                used_questions=used_q,
                used_answers=used_a,
            )

            for item in batch:
                question = normalise(item["question"])
                answer = normalise(item["answer"])
                fact = normalise(item.get("fun_fact", "")) or None

                qk, ak = dedupe_key(question), dedupe_key(answer)
                if not question or not answer or qk in seen_q or ak in seen_a:
                    continue

                seen_q.add(qk)
                seen_a.add(ak)
                used_q.append(question)
                used_a.append(answer)
                accepted.append({"question": question, "answer": answer, "fun_fact": fact})

                if len(accepted) == per_chapter:
                    break

            if len(accepted) < per_chapter and attempts < 3:
                log(
                    conn,
                    book_id,
                    f"Chapter {index} came back {per_chapter - len(accepted)} short, topping up.",
                    "warn",
                )

        if len(accepted) < per_chapter:
            raise GeminiError(
                f"Chapter {index} only produced {len(accepted)} of {per_chapter} usable questions"
            )

        rows = []
        for position, item in enumerate(accepted, start=1):
            global_no += 1
            rows.append(
                (book_id, chapter_id, global_no, index, position,
                 item["question"], item["answer"], item["fun_fact"])
            )
            all_questions.append(
                {
                    "global_no": global_no,
                    "chapter_no": index,
                    "position": position,
                    "question": item["question"],
                    "answer": item["answer"],
                }
            )

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO questions (book_id, chapter_id, global_no, chapter_no, "
                "position, question, answer, fun_fact) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )

        log(conn, book_id, f"Chapter {index} set: {len(accepted)} questions.")

    # -- 3. Answer key chapter --------------------------------------------
    key_no = chapter_count + 1
    key_title = "Answers"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO chapters (book_id, chapter_no, title, intro, is_answer_key) "
            "VALUES (%s, %s, %s, %s, 1)",
            (book_id, key_no, key_title, "Every answer, in question order."),
        )
    chapter_rows.append(
        {"chapter_no": key_no, "title": key_title, "is_answer_key": True}
    )

    # -- 4. Typeset --------------------------------------------------------
    set_status(conn, book_id, "rendering", 92, "Typesetting the PDF")
    log(conn, book_id, "Laying out pages.")

    slug = re.sub(r"[^a-z0-9]+", "-", str(book["title"]).lower()).strip("-")[:60] or "book"
    filename = f"{book_id:06d}-{slug}.pdf"
    out_path = storage_dir() / filename

    size = build_pdf(book, chapter_rows, all_questions, out_path)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE books SET status = 'done', progress = 100, stage_note = 'Ready', "
            "pdf_path = %s, pdf_bytes = %s, finished_at = NOW() WHERE id = %s",
            (filename, size, book_id),
        )

    log(conn, book_id, f"Done: {global_no} questions, {size // 1024} KB.")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_one(conn, book_id: int | None = None) -> bool:
    book = claim(conn, book_id)
    if not book:
        return False

    try:
        build_book(conn, book)
    except GeminiError as exc:
        fail(conn, int(book["id"]), str(exc))
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        fail(conn, int(book["id"]), f"{type(exc).__name__}: {exc}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Book Factory worker")
    parser.add_argument("--loop", action="store_true", help="keep polling the queue")
    parser.add_argument("--once", action="store_true", help="build one book and exit")
    parser.add_argument("--book-id", type=int, default=None, help="build this book only")
    args = parser.parse_args()

    if not args.loop and not args.once:
        parser.error("pass --loop or --once")

    conn = connect()

    if args.once:
        found = run_one(conn, args.book_id)
        if not found:
            print("Nothing queued.", flush=True)
        return 0

    print("Worker up. Polling for queued books…", flush=True)
    try:
        while True:
            if not run_one(conn):
                time.sleep(POLL_SECONDS)
            if not conn.is_connected():
                conn = connect()
    except KeyboardInterrupt:
        print("\nWorker down.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
