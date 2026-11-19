from hannibal_rerank.application.ports import PairScorer
from hannibal_rerank.application.rank import RankPassages
from hannibal_rerank.infrastructure.cross_encoder import CrossEncoderScorer
from hannibal_rerank.infrastructure.lexical import LexicalOverlapScorer
from hannibal_rerank.socle.settings import RerankSettings, ScorerKind


def build_pair_scorer(settings: RerankSettings) -> PairScorer:
    if settings.scorer is ScorerKind.LEXICAL:
        return LexicalOverlapScorer()
    return CrossEncoderScorer(
        settings.model,
        device=settings.device,
        half_precision=settings.half_precision,
        batch_size=settings.batch_size,
        max_length=settings.max_length,
    )


def build_rank_passages(settings: RerankSettings, scorer: PairScorer) -> RankPassages:
    return RankPassages(
        scorer,
        max_queries=settings.max_queries,
        max_passages=settings.max_passages,
        max_passage_chars=settings.max_passage_chars,
    )
