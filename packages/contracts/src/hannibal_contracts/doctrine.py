"""Doctrine : contrat public (`/v1/doctrine`, `/v1/glossary`) et contrat interne `api` → `doctrine`.

Une réponse n'est donnée que si chaque phrase cite un extrait et passe la validation des preuves ;
sinon le service refuse et dit pourquoi (`refusal_reason`).
"""

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from hannibal_contracts.base import ContractModel


class AnswerLanguage(StrEnum):
    FR = "fr"
    EN = "en"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    REFUSED = "refused"


class RefusalReason(StrEnum):
    """Contrôle qui a refusé, dans l'ordre de la validation des preuves (architecture 1.1.0 § 7)."""

    NO_EVIDENCE = "no_evidence"
    UNGROUNDED_CLAIM = "ungrounded_claim"
    UNSUPPORTED_ANSWER = "unsupported_answer"


class Citation(ContractModel):
    number: int = Field(ge=1, description="Numéro de l'extrait, tel qu'écrit dans la réponse : [1], [2]…")
    passage_id: int
    publication: str
    edition: str | None = None
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    title: str | None = None
    page: str | None = None
    pdf_page: int | None = None
    text: str = Field(description="Texte de l'extrait, à vérifier sur la publication")
    table_row: str | None = Field(default=None, description="Ligne de tableau la plus proche de la question")


class TermProposal(ContractModel):
    term: str
    en: str | None = None
    fr: str | None = None


class TermSuggestion(ContractModel):
    """Terme absent des publications et termes proches : l'opérateur choisit, rien n'est corrigé seul."""

    unknown: str
    proposals: list[TermProposal]


class AskRequest(ContractModel):
    """Interne : l'API a déjà décidé des publications autorisées pour le rôle."""

    question: str = Field(min_length=2, max_length=1000)
    language: AnswerLanguage = AnswerLanguage.FR
    publications: list[str] = Field(default_factory=list, description="Restriction ; vide = toutes")
    include_classified: bool = False


class AskResponse(ContractModel):
    status: AnswerStatus
    answer: str
    refusal_reason: RefusalReason | None = None
    refusal_detail: str | None = Field(default=None, description="Motif lisible, pour l'opérateur")
    citations: list[Citation] = Field(description="Extraits cités par la réponse (vide en cas de refus)")
    unknown_terms: list[str] = Field(default_factory=list)
    suggestions: list[TermSuggestion] = Field(default_factory=list)
    query_en: str | None = Field(default=None, description="Reformulation anglaise utilisée pour chercher")
    model: str
    index_version: str
    thresholds: dict[str, float]
    second_try: bool = False
    duration_ms: int


class DoctrineQuestion(ContractModel):
    question: str = Field(min_length=2, max_length=1000)
    language: AnswerLanguage = AnswerLanguage.FR
    publication: str | None = Field(default=None, description="Restreint la recherche à une publication")


class DoctrineAnswer(AskResponse):
    trace_id: UUID = Field(description="Ligne de `ops.doctrine_traces` qui garde cette réponse")


class Publications(ContractModel):
    publications: list[str] = Field(description="Publications consultables avec le rôle courant")


class GlossaryEntry(ContractModel):
    en: str
    fr: str | None = None
    sense: int | None = None
    abbreviation: str | None = None
    definition_en: str | None = None
    definition_fr: str | None = None
    source: str
    page: str | None = None
    status: str | None = None


class GlossaryResult(ContractModel):
    query: str
    entries: list[GlossaryEntry]


class ExplainRequest(ContractModel):
    """Interne : l'ordre et l'interprétation déterministe que l'explication ne doit pas contredire."""

    message: str = Field(min_length=1, max_length=500)
    meaning_en: str = Field(description="Interprétation déterministe, en anglais")
    meaning_fr: str = Field(description="Interprétation déterministe, en français")
    parameters: dict[str, int | str] = Field(
        default_factory=dict,
        description="Paramètres décodés : side, true_course, relative_degrees, speed_knots…",
    )


class ExplanationSource(StrEnum):
    CHECKED_MODEL = "checked_model"
    DETERMINISTIC = "deterministic"


class Explanation(ContractModel):
    explanation_en: str
    explanation_fr: str
    source: ExplanationSource = Field(
        description="`deterministic` : texte du modèle refusé par les contrôles, on rend l'interprétation"
    )
    citations: list[Citation] = Field(default_factory=list)
    rejected_checks: list[str] = Field(default_factory=list, description="Contrôles échoués par le modèle")
    model: str
    duration_ms: int


class CommandExplanation(Explanation):
    command_id: UUID
