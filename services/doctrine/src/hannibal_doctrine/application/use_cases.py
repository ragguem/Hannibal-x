from dataclasses import dataclass

from hannibal_doctrine.application.ask import AskDoctrine
from hannibal_doctrine.application.explain import ExplainOrder
from hannibal_doctrine.application.glossary import LookupGlossary
from hannibal_doctrine.application.ports import PassageIndex


@dataclass(frozen=True, slots=True)
class DoctrineUseCases:
    ask: AskDoctrine
    lookup_glossary: LookupGlossary
    explain_order: ExplainOrder
    index: PassageIndex
    classified_publications: tuple[str, ...]
