"""Rédaction d'une réponse citée (`verify`) ou appuyée sur des citations mot pour mot (`quotes`)."""

import json
import re
from dataclasses import dataclass, field

from hannibal_core.grounding.evidence import NOT_FOUND_PATTERN

from hannibal_contracts.doctrine import AnswerLanguage, RefusalReason
from hannibal_doctrine.application.extracts import CITATION, Extract, cited_numbers
from hannibal_doctrine.application.ports import ChatModel, DependencyDown
from hannibal_doctrine.application.prompts import (
    CITATION_REMINDER,
    CITED_ANSWER_SYSTEM,
    NO_SOURCE_MARKER,
    QUOTED_ANSWER_SYSTEM,
)
from hannibal_doctrine.application.refusal import (
    NO_EXACT_QUOTE,
    NO_VALID_CITATION,
    NOT_FOUND_IN_EXTRACTS,
    UNREADABLE_ANSWER,
    Refusal,
)

DODGE = re.compile(
    r"(does|do|did) not (specify|mention|state|provide|indicate)|not specified|no information"
    r"|ne (précise|mentionne|spécifie|indique|fourni\w*) pas|n'est pas (précisé|mentionné|spécifié|indiqué)"
    r"|aucune information",
    re.I,
)
MAX_QUOTES = 4
MIN_QUOTE_WORDS = 4
QUOTE_RUN_WORDS = 6
MAX_QUOTE_CHARS = 400


@dataclass(frozen=True, slots=True)
class Draft:
    text: str
    cited: list[int]
    refusal: Refusal | None = None
    quotes: list[tuple[int, str]] = field(default_factory=list)


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def quote_found_in(quote: str, extract_text: str) -> bool:
    """Toute la citation, ou au moins une suite de 6 mots identiques, se retrouve dans l'extrait."""
    body = normalized(extract_text)
    words = quote.split()
    return quote in body or any(
        " ".join(words[i : i + QUOTE_RUN_WORDS]) in body
        for i in range(max(1, len(words) - QUOTE_RUN_WORDS + 1))
    )


def question_prompt(context: str, question: str) -> str:
    return f"Extraits :\n\n{context}\n\nQuestion : {question}"


class AnswerDrafter:
    def __init__(self, chat: ChatModel, *, reasoning: bool | None) -> None:
        self._chat = chat
        self._reasoning = reasoning

    async def cited_answer(
        self,
        question: str,
        language: AnswerLanguage,
        extracts: list[Extract],
        context: str,
        *,
        model: str | None = None,
        reasoning: bool | None = None,
    ) -> Draft:
        system = CITED_ANSWER_SYSTEM[language]
        user = question_prompt(context, question)
        think = None if model else (self._reasoning if reasoning is None else reasoning)
        answer = (await self._chat.chat(system, user, model=model, reasoning=think)).strip()
        cited, outside = cited_numbers(answer, len(extracts))
        if NO_SOURCE_MARKER not in answer and (not cited or outside):
            reminder = CITATION_REMINDER.format(count=len(extracts))
            answer = (await self._chat.chat(system + reminder, user, model=model)).strip()
            cited, outside = cited_numbers(answer, len(extracts))
        if NO_SOURCE_MARKER in answer or DODGE.search(answer):
            return Draft(answer, [], Refusal(RefusalReason.NO_EVIDENCE, NOT_FOUND_IN_EXTRACTS))
        if not cited or outside:
            return Draft(answer, [], Refusal(RefusalReason.UNSUPPORTED_ANSWER, NO_VALID_CITATION))
        return Draft(answer, cited)

    async def quoted_answer(
        self, question: str, language: AnswerLanguage, extracts: list[Extract], context: str
    ) -> Draft:
        """Le programme vérifie que chaque citation figure bien dans l'extrait indiqué."""
        try:
            raw = await self._chat.chat(
                QUOTED_ANSWER_SYSTEM[language],
                question_prompt(context, question),
                output="json",
                reasoning=self._reasoning,
            )
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError(type(data).__name__)
        except DependencyDown:
            raise
        except (ValueError, TypeError):
            return Draft("", [], Refusal(RefusalReason.UNSUPPORTED_ANSWER, UNREADABLE_ANSWER))
        answer = str(data.get("answer") or "").strip()
        good: list[tuple[int, str]] = []
        for item in (data.get("quotes") or [])[:MAX_QUOTES]:
            if not isinstance(item, dict):
                continue
            try:
                number = int(item.get("n", ""))
            except (TypeError, ValueError):
                continue
            quote = normalized(str(item.get("text") or ""))
            if not 1 <= number <= len(extracts) or len(quote.split()) < MIN_QUOTE_WORDS:
                continue
            if quote_found_in(quote, extracts[number - 1].passage.text):
                good.append((number, str(item.get("text"))[:MAX_QUOTE_CHARS]))
        if NO_SOURCE_MARKER in answer or not answer:
            return Draft(answer, [], Refusal(RefusalReason.NO_EVIDENCE, NOT_FOUND_IN_EXTRACTS))
        if not good:
            return Draft(answer, [], Refusal(RefusalReason.UNSUPPORTED_ANSWER, NO_EXACT_QUOTE))
        quoted = sorted({number for number, _ in good})
        cited = sorted({int(n) for n in CITATION.findall(answer) if 1 <= int(n) <= len(extracts)})
        if not cited or not set(cited) <= set(quoted):
            cited = quoted
            answer = re.sub(r"\s*\[\d+\]", "", answer).strip() + " " + "".join(f"[{n}]" for n in quoted)
        if NOT_FOUND_PATTERN.search(answer):
            return Draft(answer, [], Refusal(RefusalReason.NO_EVIDENCE, NOT_FOUND_IN_EXTRACTS))
        return Draft(answer, cited, quotes=good)
