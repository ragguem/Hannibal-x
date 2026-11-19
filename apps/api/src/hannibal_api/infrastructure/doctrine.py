"""Assistant de doctrine : client du service `doctrine` (mode `real`) et assistant d'exemple (mode `fake`)."""

import httpx

from hannibal_contracts.doctrine import (
    AnswerStatus,
    AskRequest,
    AskResponse,
    Citation,
    ExplainRequest,
    Explanation,
    ExplanationSource,
    GlossaryEntry,
    GlossaryResult,
    Publications,
    RefusalReason,
)
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_client import InternalClient

DEPENDENCY = "doctrine"


class DoctrineClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = InternalClient(
            DEPENDENCY, base_url, token=token, timeout_s=timeout_s, transport=transport
        )

    @staticmethod
    def _checked(response: httpx.Response) -> bytes:
        if response.status_code >= 400:
            raise DependencyUnavailable(DEPENDENCY, f"réponse {response.status_code}")
        return response.content

    async def ask(self, request: AskRequest) -> AskResponse:
        response = await self._client.post("/ask", json=request.model_dump(mode="json"))
        return AskResponse.model_validate_json(self._checked(response))

    async def glossary(self, query: str) -> GlossaryResult:
        response = await self._client.get("/glossary", params={"q": query})
        return GlossaryResult.model_validate_json(self._checked(response))

    async def publications(self, *, include_classified: bool) -> list[str]:
        response = await self._client.get(
            "/publications", params={"include_classified": str(include_classified).lower()}
        )
        return Publications.model_validate_json(self._checked(response)).publications

    async def explain(self, request: ExplainRequest) -> Explanation:
        response = await self._client.post("/explain", json=request.model_dump(mode="json"))
        return Explanation.model_validate_json(self._checked(response))

    async def aclose(self) -> None:
        await self._client.aclose()


SAMPLE_PUBLICATION = "DEMO-MANUEL"
SAMPLE_RESTRICTED = "DEMO-RESTREINT"
SAMPLE_PASSAGE = Citation(
    number=1,
    passage_id=2,
    publication=SAMPLE_PUBLICATION,
    article="102",
    title="Formation speed",
    page="1-4",
    text="The standard tactical speed is 12 knots unless another speed is ordered.",
)


class SampleDoctrine:
    """Texte inventé : répond aux questions sur la vitesse, refuse le reste. Pour le poste et les tests."""

    def __init__(self) -> None:
        self.requests: list[AskRequest] = []

    async def ask(self, request: AskRequest) -> AskResponse:
        self.requests.append(request)
        common = {"model": "sample", "index_version": "sample-1", "thresholds": {"min_similarity": 0.45}}
        if "speed" in request.question.lower() or "vitesse" in request.question.lower():
            return AskResponse(
                status=AnswerStatus.ANSWERED,
                answer="The standard tactical speed is 12 knots unless another speed is ordered [1].",
                citations=[SAMPLE_PASSAGE],
                duration_ms=40,
                **common,
            )
        return AskResponse(
            status=AnswerStatus.REFUSED,
            answer="Je ne trouve pas cette information dans les publications chargées.",
            refusal_reason=RefusalReason.NO_EVIDENCE,
            refusal_detail="aucun passage assez proche",
            citations=[],
            duration_ms=20,
            **common,
        )

    async def glossary(self, query: str) -> GlossaryResult:
        entry = GlossaryEntry(
            en="replenishment at sea",
            fr="ravitaillement à la mer",
            abbreviation="RAS",
            source="DEMO-GLOSSAIRE",
        )
        found = query and any(query in (v or "").lower() for v in (entry.en, entry.fr, entry.abbreviation))
        return GlossaryResult(query=query, entries=[entry] if found else [])

    async def publications(self, *, include_classified: bool) -> list[str]:
        return [SAMPLE_PUBLICATION, SAMPLE_RESTRICTED] if include_classified else [SAMPLE_PUBLICATION]

    async def explain(self, request: ExplainRequest) -> Explanation:
        return Explanation(
            explanation_en=request.meaning_en,
            explanation_fr=request.meaning_fr,
            source=ExplanationSource.DETERMINISTIC,
            model="sample",
            duration_ms=5,
        )
