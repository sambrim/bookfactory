"""Typesetting for Book Factory.

The house standard is fixed: 3 questions per page, 10 pages per chapter, answer
key last. That means pagination is arithmetic, not flow — we place questions on
a fixed three-slot grid rather than letting a layout engine decide. Slots are
generous enough for a 220-character question, which is the cap the writer prompt
enforces.

Uses reportlab's base-14 fonts only, so there are no font files to ship.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

# --- palette, matching the web UI -------------------------------------------
INK       = Color(0.086, 0.075, 0.059)
ASH       = Color(0.424, 0.404, 0.361)
BLUE      = Color(0.122, 0.208, 0.961)
VERMILION = Color(1.000, 0.290, 0.110)
RULE      = Color(0.827, 0.816, 0.776)

PAGE_W, PAGE_H = A5
MARGIN_X = 16 * mm
MARGIN_TOP = 18 * mm
MARGIN_BOTTOM = 16 * mm
CONTENT_W = PAGE_W - (2 * MARGIN_X)

BODY = "Helvetica"
BODY_BOLD = "Helvetica-Bold"
DISPLAY = "Helvetica-Bold"
UTIL = "Helvetica"


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy wrap on a fixed width. Long unbroken tokens are hard-split."""
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        # A single word wider than the column: split it.
        while pdfmetrics.stringWidth(word, font, size) > width:
            cut = len(word)
            while cut > 1 and pdfmetrics.stringWidth(word[:cut] + "-", font, size) > width:
                cut -= 1
            lines.append(word[:cut] + "-")
            word = word[cut:]
        current = word

    if current:
        lines.append(current)
    return lines or [""]


class BookPDF:
    def __init__(self, book: dict[str, Any]) -> None:
        self.book = book
        self.title = str(book["title"])
        self.theme = str(book["theme_label"])
        self.chapter_count = int(book["chapter_count"])
        self.pages_per_chapter = int(book["pages_per_chapter"])
        self.per_page = int(book["questions_per_page"])
        self.printed_page = 0  # numbering starts on the first question page

    # -- primitives --------------------------------------------------------

    def _rule(self, c: rl_canvas.Canvas, y: float, colour: Color = RULE, weight: float = 0.6) -> None:
        c.setStrokeColor(colour)
        c.setLineWidth(weight)
        c.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)

    def _registration_mark(
        self,
        c: rl_canvas.Canvas,
        x: float,
        y: float,
        r: float = 4 * mm,
        ring: Color = VERMILION,
        cross: Color = BLUE,
    ) -> None:
        c.setLineWidth(0.8)
        c.setStrokeColor(ring)
        c.circle(x, y, r, stroke=1, fill=0)
        c.setStrokeColor(cross)
        c.line(x, y - r - 2 * mm, x, y + r + 2 * mm)
        c.line(x - r - 2 * mm, y, x + r + 2 * mm, y)

    def _running_head(self, c: rl_canvas.Canvas, chapter_title: str) -> None:
        y = PAGE_H - MARGIN_TOP + 6 * mm
        c.setFont(UTIL, 7)
        c.setFillColor(ASH)
        c.drawString(MARGIN_X, y, self.title.upper()[:44])
        c.drawRightString(PAGE_W - MARGIN_X, y, chapter_title.upper()[:38])
        self._rule(c, y - 2.5 * mm)

    def _folio(self, c: rl_canvas.Canvas) -> None:
        self.printed_page += 1
        c.setFont(UTIL, 8)
        c.setFillColor(ASH)
        c.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM - 6 * mm, str(self.printed_page))

    # -- front matter ------------------------------------------------------

    def cover(self, c: rl_canvas.Canvas, total_questions: int) -> None:
        # Solid blue field with a vermilion band: the overprint motif.
        c.setFillColor(BLUE)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        c.setFillColor(VERMILION)
        c.rect(0, PAGE_H - 46 * mm, PAGE_W, 10 * mm, stroke=0, fill=1)

        c.setFillColor(Color(1, 1, 1))
        c.setFont(UTIL, 8)
        c.drawString(MARGIN_X, PAGE_H - 24 * mm, "BOOK FACTORY")
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 24 * mm, self.theme.upper())

        # Title, set as large as it fits on up to four lines.
        size = 34.0
        lines = wrap(self.title, DISPLAY, size, CONTENT_W)
        while len(lines) > 4 and size > 16:
            size -= 2
            lines = wrap(self.title, DISPLAY, size, CONTENT_W)

        # Centre the block in the field between the vermilion band and the
        # imprint line, so short and long titles both sit deliberately.
        field_top = PAGE_H - 56 * mm
        field_bottom = 44 * mm
        block_h = len(lines) * size * 1.02
        y = ((field_top + field_bottom) / 2) + (block_h / 2) - size

        c.setFont(DISPLAY, size)
        for line in lines:
            c.drawString(MARGIN_X, y, line)
            y -= size * 1.02

        c.setFont(UTIL, 9)
        c.drawString(
            MARGIN_X,
            34 * mm,
            f"{total_questions} questions across {self.chapter_count} chapters",
        )
        c.drawString(MARGIN_X, 29 * mm, f"Answers at the back  ·  {date.today().isoformat()}")

        self._registration_mark(
            c,
            PAGE_W - MARGIN_X - 5 * mm,
            32 * mm,
            ring=Color(1, 1, 1),
            cross=VERMILION,
        )
        c.showPage()

    def contents(self, c: rl_canvas.Canvas, chapters: list[dict[str, Any]]) -> None:
        c.setFillColor(INK)
        c.setFont(DISPLAY, 20)
        c.drawString(MARGIN_X, PAGE_H - MARGIN_TOP - 6 * mm, "Contents")
        self._rule(c, PAGE_H - MARGIN_TOP - 12 * mm, INK, 1.2)

        y = PAGE_H - MARGIN_TOP - 24 * mm
        for chapter in chapters:
            no = int(chapter["chapter_no"])
            is_key = bool(chapter.get("is_answer_key"))
            start = (
                (self.chapter_count * self.pages_per_chapter) + 1
                if is_key
                else ((no - 1) * self.pages_per_chapter) + 1
            )

            c.setFont(UTIL, 8)
            c.setFillColor(BLUE if is_key else VERMILION)
            c.drawString(MARGIN_X, y, f"{no:02d}")

            c.setFont(BODY, 10.5)
            c.setFillColor(INK)
            title_lines = wrap(str(chapter["title"]), BODY, 10.5, CONTENT_W - 24 * mm)
            c.drawString(MARGIN_X + 10 * mm, y, title_lines[0])

            c.setFont(UTIL, 9)
            c.setFillColor(ASH)
            c.drawRightString(PAGE_W - MARGIN_X, y, str(start))

            y -= 8 * mm
            if y < MARGIN_BOTTOM + 10 * mm:
                break

        c.setFont(UTIL, 7.5)
        c.setFillColor(ASH)
        c.drawString(
            MARGIN_X,
            MARGIN_BOTTOM,
            f"{self.per_page} questions per page  ·  {self.pages_per_chapter} pages per chapter",
        )
        c.showPage()

    # -- question pages ----------------------------------------------------

    def question_pages(
        self,
        c: rl_canvas.Canvas,
        chapter: dict[str, Any],
        questions: list[dict[str, Any]],
    ) -> None:
        title = str(chapter["title"])
        slots_per_page = self.per_page
        pages = self.pages_per_chapter

        # Fixed three-slot grid. Height is what's left after head and folio.
        usable_top = PAGE_H - MARGIN_TOP
        usable_bottom = MARGIN_BOTTOM + 4 * mm
        slot_h = (usable_top - usable_bottom) / slots_per_page

        for page_index in range(pages):
            batch = questions[page_index * slots_per_page : (page_index + 1) * slots_per_page]
            if not batch and page_index > 0:
                break

            self._running_head(c, title)

            if page_index == 0:
                # Chapter opener sits above the first slot.
                c.setFillColor(VERMILION)
                c.setFont(UTIL, 8)
                c.drawString(MARGIN_X, usable_top - 6 * mm, f"CHAPTER {int(chapter['chapter_no']):02d}")

                c.setFillColor(INK)
                c.setFont(DISPLAY, 15)
                head_lines = wrap(title, DISPLAY, 15, CONTENT_W)
                hy = usable_top - 13 * mm
                for line in head_lines[:2]:
                    c.drawString(MARGIN_X, hy, line)
                    hy -= 6.5 * mm

                top = hy - 3 * mm
                slot_h_first = (top - usable_bottom) / slots_per_page
            else:
                top = usable_top - 4 * mm
                slot_h_first = slot_h

            for slot, item in enumerate(batch):
                slot_top = top - (slot * slot_h_first)
                self._draw_question(c, item, slot_top, slot_h_first)

            self._folio(c)
            c.showPage()

    def _draw_question(
        self,
        c: rl_canvas.Canvas,
        item: dict[str, Any],
        slot_top: float,
        slot_h: float,
    ) -> None:
        number = int(item["global_no"])
        text = str(item["question"])

        # Number in the left rail.
        c.setFillColor(BLUE)
        c.setFont(DISPLAY, 13)
        c.drawString(MARGIN_X, slot_top - 4.4 * mm, str(number))

        rail = 12 * mm
        body_w = CONTENT_W - rail

        c.setFillColor(INK)
        size = 10.5
        lines = wrap(text, BODY, size, body_w)
        while len(lines) > 5 and size > 8:
            size -= 0.5
            lines = wrap(text, BODY, size, body_w)

        c.setFont(BODY, size)
        y = slot_top - 4.4 * mm
        for line in lines:
            c.drawString(MARGIN_X + rail, y, line)
            y -= size * 1.28

        # Writing rule, pinned to the foot of the slot rather than to the end of
        # the question, so all three rules on a page share one baseline rhythm.
        line_y = slot_top - slot_h + 10 * mm
        if line_y > y - 3 * mm:          # very long question: drop below the text
            line_y = y - 3 * mm

        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.setDash(1, 2.2)
        c.line(MARGIN_X + rail, line_y, PAGE_W - MARGIN_X, line_y)
        c.setDash()

    # -- answer key --------------------------------------------------------

    def answer_key(
        self,
        c: rl_canvas.Canvas,
        chapters: list[dict[str, Any]],
        answers_by_chapter: dict[int, list[dict[str, Any]]],
        key_title: str,
    ) -> None:
        col_w = (CONTENT_W - 8 * mm) / 2
        col_x = [MARGIN_X, MARGIN_X + col_w + 8 * mm]
        top = PAGE_H - MARGIN_TOP - 14 * mm
        bottom = MARGIN_BOTTOM + 4 * mm

        col = 0
        y = top
        first_page = True

        def new_page() -> None:
            nonlocal col, y, first_page
            self._folio(c)
            c.showPage()
            self._running_head(c, key_title)
            col = 0
            y = PAGE_H - MARGIN_TOP - 6 * mm
            first_page = False

        self._running_head(c, key_title)
        c.setFillColor(BLUE)
        c.setFont(UTIL, 8)
        c.drawString(MARGIN_X, PAGE_H - MARGIN_TOP - 4 * mm, "ANSWER KEY")
        c.setFillColor(INK)
        c.setFont(DISPLAY, 15)
        c.drawString(MARGIN_X, PAGE_H - MARGIN_TOP - 11 * mm, key_title)

        for chapter in chapters:
            if chapter.get("is_answer_key"):
                continue
            no = int(chapter["chapter_no"])
            items = answers_by_chapter.get(no, [])
            if not items:
                continue

            # Chapter heading in the key.
            if y - 8 * mm < bottom:
                if col == 0:
                    col, y = 1, top if first_page else PAGE_H - MARGIN_TOP - 6 * mm
                else:
                    new_page()

            c.setFillColor(VERMILION)
            c.setFont(UTIL, 7.5)
            c.drawString(col_x[col], y, f"CHAPTER {no:02d} · {str(chapter['title']).upper()[:30]}")
            y -= 5 * mm

            for item in items:
                if y < bottom:
                    if col == 0:
                        col = 1
                        y = top if first_page else PAGE_H - MARGIN_TOP - 6 * mm
                    else:
                        new_page()

                label = f"{int(item['global_no'])}."
                c.setFillColor(BLUE)
                c.setFont(UTIL, 8)
                c.drawString(col_x[col], y, label)

                indent = pdfmetrics.stringWidth("999. ", UTIL, 8)
                c.setFillColor(INK)
                lines = wrap(str(item["answer"]), BODY, 8.5, col_w - indent)
                c.setFont(BODY, 8.5)
                for line in lines[:3]:
                    c.drawString(col_x[col] + indent, y, line)
                    y -= 4.4 * mm

            y -= 2 * mm

        self._folio(c)
        c.showPage()


def build_pdf(
    book: dict[str, Any],
    chapters: list[dict[str, Any]],
    questions: Iterable[dict[str, Any]],
    out_path: Path,
) -> int:
    """Render the whole book. Returns the file size in bytes."""
    questions = list(questions)
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    for q in questions:
        by_chapter.setdefault(int(q["chapter_no"]), []).append(q)
    for items in by_chapter.values():
        items.sort(key=lambda item: int(item["position"]))

    doc = BookPDF(book)
    c = rl_canvas.Canvas(str(out_path), pagesize=A5)
    c.setTitle(str(book["title"]))
    c.setAuthor("Book Factory")
    c.setSubject(f"{book['theme_label']} trivia")

    doc.cover(c, len(questions))
    doc.contents(c, chapters)

    key_chapter = next((ch for ch in chapters if ch.get("is_answer_key")), None)

    for chapter in chapters:
        if chapter.get("is_answer_key"):
            continue
        doc.question_pages(c, chapter, by_chapter.get(int(chapter["chapter_no"]), []))

    doc.answer_key(
        c,
        chapters,
        by_chapter,
        str(key_chapter["title"]) if key_chapter else "Answers",
    )

    c.save()
    return out_path.stat().st_size
