from dataclasses import dataclass

from hannibal_contracts.doctrine import RefusalReason

NOT_FOUND_IN_EXTRACTS = "le modèle ne trouve pas la réponse dans les extraits"
NO_CLOSE_PASSAGE = "aucun passage assez proche"
NO_VALID_CITATION = "réponse sans citation valide"
UNREADABLE_ANSWER = "réponse du modèle illisible"
NO_EXACT_QUOTE = "aucune citation exacte à l'appui"


@dataclass(frozen=True, slots=True)
class Refusal:
    reason: RefusalReason
    detail: str
