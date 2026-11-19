import json
from dataclasses import dataclass, field

from hannibal_doctrine.application.ports import ChatModel, DependencyDown
from hannibal_doctrine.application.prompts import REWRITE_SYSTEM

MAX_KEYWORDS = 8


@dataclass(frozen=True, slots=True)
class Rewrite:
    query_en: str = ""
    keywords: list[str] = field(default_factory=list)


class QueryRewriter:
    """Reformule la question en anglais doctrinal (le corpus est en anglais). En cas d'échec : rien."""

    def __init__(self, chat: ChatModel, *, reasoning: bool | None) -> None:
        self._chat = chat
        self._reasoning = reasoning

    async def __call__(self, question: str) -> Rewrite:
        try:
            raw = await self._chat.chat(REWRITE_SYSTEM, question, output="json", reasoning=self._reasoning)
            data = json.loads(raw)
        except (DependencyDown, ValueError):
            return Rewrite()
        if not isinstance(data, dict):
            return Rewrite()
        keywords = data.get("keywords") or []
        return Rewrite(
            query_en=str(data.get("query") or "").strip(),
            keywords=[str(k) for k in keywords][:MAX_KEYWORDS] if isinstance(keywords, list) else [],
        )
