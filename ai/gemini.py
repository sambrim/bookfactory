"""Gemini calls for Book Factory.

Two prompts:
  * research_theme()      — one grounded pass that maps the subject and names
                            the chapters, so questions don't drift.
  * write_chapter()       — one call per chapter, returning exactly N Q&A pairs.

Model notes for gemini-3.5-flash-lite: temperature / top_p / top_k are
deprecated and ignored, so determinism comes from the system instruction
instead. thinking_level is set explicitly because Flash-Lite defaults to
"minimal", which is too shallow for the research pass.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

from google import genai

from bfconfig import cfg, cfg_bool


class GeminiError(RuntimeError):
    pass


SYSTEM_RESEARCH = """You are the research desk of a trivia book publisher.
You map a subject before any questions are written.

Rules:
- Only state facts you are confident are true and verifiable. Accuracy beats interest.
- Avoid anything still in flux: live scores, current office-holders, this year's
  records. Prefer settled facts that will still be correct in five years.
- Chapter angles must not overlap. Each covers a different slice of the subject.
- Reply with JSON only, matching the schema. No commentary.
"""

SYSTEM_WRITER = """You write trivia questions for printed quiz books.

Rules for every question:
- One unambiguous answer. If two answers could be defended, rewrite the question.
- Self-contained: no "as mentioned earlier", no reference to other questions.
- Under 220 characters. Plain sentences, no multiple choice, no true/false runs.
- The answer is a short phrase, not a sentence. Under 90 characters.
- Never repeat a question already used in this book, and never ask two questions
  with the same answer.
- No questions whose answer changes over time.
- fun_fact is one extra sentence of context, under 160 characters. It must not
  give away another question's answer.
- Write in plain English with no emoji and no markdown.
- Reply with JSON only, matching the schema. No commentary.
"""

RESEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "150-250 words mapping the subject: eras, key names, "
                           "landmark events, common misconceptions.",
        },
        "chapters": {
            "type": "array",
            "description": "One entry per requested chapter, in reading order.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Chapter title, under 60 characters, no numbering.",
                    },
                    "angle": {
                        "type": "string",
                        "description": "One sentence on what this chapter covers "
                                       "and what it deliberately leaves out.",
                    },
                },
                "required": ["title", "angle"],
            },
        },
    },
    "required": ["summary", "chapters"],
}


def chapter_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                        "fun_fact": {"type": "string"},
                    },
                    "required": ["question", "answer"],
                },
            }
        },
        "required": ["questions"],
    }


class GeminiWriter:
    def __init__(self) -> None:
        api_key = cfg("GEMINI_API_KEY")
        if not api_key or api_key == "your-key-here":
            raise GeminiError("GEMINI_API_KEY is not set in .env")

        self.client = genai.Client(api_key=api_key)
        self.model = str(cfg("GEMINI_MODEL", "gemini-3.5-flash-lite"))
        self.use_search = cfg_bool("GEMINI_USE_SEARCH", True)
        self.thinking_research = str(cfg("GEMINI_THINKING_RESEARCH", "medium"))
        self.thinking_writing = str(cfg("GEMINI_THINKING_WRITING", "low"))

    # -- low level ---------------------------------------------------------

    def _create(
        self,
        prompt: str,
        system: str,
        schema: dict[str, Any],
        thinking: str,
        tools: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "system_instruction": system,
            "thinking_level": thinking,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        }
        if tools:
            kwargs["tools"] = tools

        interaction = self.client.interactions.create(**kwargs)
        text = (interaction.output_text or "").strip()
        if not text:
            raise GeminiError("Gemini returned an empty response")

        # Belt and braces: strip fences if the model ever wraps the JSON.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"Gemini returned malformed JSON: {exc}") from exc

    def _with_retries(self, describe: str, fn, attempts: int = 3) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — surfaced to the job log
                last = exc
                if attempt == attempts:
                    break
                delay = (2 ** attempt) + random.uniform(0, 1.5)
                time.sleep(delay)
        raise GeminiError(f"{describe} failed after {attempts} attempts: {last}")

    # -- high level --------------------------------------------------------

    def research_theme(
        self,
        theme: str,
        title: str,
        chapter_count: int,
        difficulty: str,
    ) -> dict[str, Any]:
        prompt = (
            f"Subject: {theme}\n"
            f"Book title: {title}\n"
            f"Difficulty: {difficulty}\n"
            f"Chapters needed: {chapter_count}\n\n"
            f"Map this subject for a trivia book, then propose exactly "
            f"{chapter_count} chapters that between them cover it broadly. "
            f"Order them so a reader warms up before the harder material. "
            f"Titles should read like book chapters, not category labels."
        )

        tools = [{"type": "google_search"}] if self.use_search else None

        def call_with_tools() -> dict[str, Any]:
            return self._create(
                prompt, SYSTEM_RESEARCH, RESEARCH_SCHEMA, self.thinking_research, tools
            )

        try:
            data = self._with_retries("Research pass", call_with_tools)
        except GeminiError:
            if not tools:
                raise
            # Grounding can be unavailable on some keys — fall back ungrounded.
            data = self._with_retries(
                "Research pass (ungrounded)",
                lambda: self._create(
                    prompt, SYSTEM_RESEARCH, RESEARCH_SCHEMA, self.thinking_research
                ),
            )

        chapters = data.get("chapters") or []
        if len(chapters) < chapter_count:
            # Pad rather than fail; the writer prompt still has the angle text.
            for i in range(len(chapters), chapter_count):
                chapters.append(
                    {"title": f"{theme}, part {i + 1}", "angle": f"General {theme} questions."}
                )
        data["chapters"] = chapters[:chapter_count]
        return data

    def write_chapter(
        self,
        *,
        theme: str,
        book_title: str,
        difficulty: str,
        brief: str,
        chapter_no: int,
        chapter_total: int,
        chapter_title: str,
        chapter_angle: str,
        count: int,
        used_questions: list[str],
        used_answers: list[str],
    ) -> list[dict[str, str]]:
        difficulty_note = {
            "easy": "Aim for questions a casual quizzer gets right most of the time.",
            "mixed": "Mix gentle openers with a few that will stump most people.",
            "hard": "Aim high: specialist knowledge, but never obscure for its own sake.",
        }.get(difficulty, "Mix gentle openers with a few that will stump most people.")

        avoid_q = "\n".join(f"- {q}" for q in used_questions[-120:])
        avoid_a = ", ".join(used_answers[-120:])

        prompt = (
            f"Book: {book_title}\n"
            f"Subject: {theme}\n"
            f"Chapter {chapter_no} of {chapter_total}: {chapter_title}\n"
            f"This chapter covers: {chapter_angle}\n\n"
            f"Research brief for the whole book:\n{brief}\n\n"
            f"Write exactly {count} trivia questions for this chapter only. "
            f"{difficulty_note}\n"
            f"Order them so the chapter opens easier and closes harder.\n"
        )

        if avoid_q:
            prompt += f"\nAlready used in earlier chapters, do not repeat or rephrase:\n{avoid_q}\n"
        if avoid_a:
            prompt += f"\nAnswers already used, pick different ones: {avoid_a}\n"

        data = self._with_retries(
            f"Chapter {chapter_no}",
            lambda: self._create(
                prompt,
                SYSTEM_WRITER,
                chapter_schema(count),
                self.thinking_writing,
            ),
        )

        questions = data.get("questions") or []
        cleaned: list[dict[str, str]] = []
        for item in questions:
            q = str(item.get("question", "")).strip()
            a = str(item.get("answer", "")).strip()
            if not q or not a:
                continue
            cleaned.append(
                {
                    "question": q,
                    "answer": a,
                    "fun_fact": str(item.get("fun_fact", "")).strip() or "",
                }
            )

        if not cleaned:
            raise GeminiError(f"Chapter {chapter_no} came back with no usable questions")

        return cleaned

    def top_up(self, *, shortfall: int, **kwargs: Any) -> list[dict[str, str]]:
        """Ask for the remainder when a chapter comes back short."""
        kwargs["count"] = shortfall
        return self.write_chapter(**kwargs)
