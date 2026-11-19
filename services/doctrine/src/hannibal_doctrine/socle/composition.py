from dataclasses import dataclass
from typing import Any

from hannibal_doctrine.application.ask import AnsweringPolicy, AskDoctrine
from hannibal_doctrine.application.drafting import AnswerDrafter
from hannibal_doctrine.application.evidence import AnswerVerifier, EvidenceValidation
from hannibal_doctrine.application.explain import ExplainOrder
from hannibal_doctrine.application.glossary import LookupGlossary
from hannibal_doctrine.application.ports import ChatModel, Embedder, GlossaryStore, PassageIndex, Reranker
from hannibal_doctrine.application.retrieve import RetrievePassages
from hannibal_doctrine.application.rewrite import QueryRewriter
from hannibal_doctrine.application.term_advice import AdviseOnTerms
from hannibal_doctrine.application.use_cases import DoctrineUseCases
from hannibal_doctrine.infrastructure.ollama import OllamaChat, OllamaEmbedder
from hannibal_doctrine.infrastructure.pg_index import PgDoctrineStore
from hannibal_doctrine.infrastructure.rerank_client import NoReranker, RerankClient
from hannibal_doctrine.infrastructure.sample import HashedWordsEmbedder, SampleCorpus, ScriptedChatModel
from hannibal_doctrine.socle.settings import AnswerStyle, DoctrineAdapters, DoctrineSettings


class MissingDatabaseUrl(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DoctrineAdaptersSet:
    index: PassageIndex
    glossary: GlossaryStore
    embedder: Embedder
    chat: ChatModel
    reranker: Reranker
    closables: tuple[Any, ...] = ()


def build_adapters(settings: DoctrineSettings) -> DoctrineAdaptersSet:
    if settings.adapters is DoctrineAdapters.SAMPLE:
        corpus = SampleCorpus(next(iter(settings.classified_publications), None))
        return DoctrineAdaptersSet(corpus, corpus, HashedWordsEmbedder(), ScriptedChatModel(), NoReranker())
    if not settings.database_dsn:
        raise MissingDatabaseUrl("HX_DOCTRINE_DATABASE_URL est requis en mode real (rôle hannibal_doctrine)")
    store = PgDoctrineStore(settings.database_dsn)
    chat = OllamaChat(
        settings.ollama_url,
        model=settings.drafting_model,
        context_window=settings.context_window,
        timeout_s=settings.chat_timeout_s,
    )
    embedder = OllamaEmbedder(
        settings.ollama_url,
        model=settings.embedding_model,
        on_cpu=settings.embeddings_on_cpu,
        timeout_s=settings.embedding_timeout_s,
    )
    token = settings.internal_token.get_secret_value() if settings.internal_token else None
    reranker: Any = (
        RerankClient(settings.rerank_url, token=token, timeout_s=settings.rerank_timeout_s)
        if settings.rerank_url
        else NoReranker()
    )
    return DoctrineAdaptersSet(store, store, embedder, chat, reranker, (store, chat, embedder, reranker))


def build_use_cases(settings: DoctrineSettings, adapters: DoctrineAdaptersSet) -> DoctrineUseCases:
    classified = tuple(settings.classified_publications)
    verifier = AnswerVerifier(adapters.chat, reasoning=settings.reasoning)
    ask = AskDoctrine(
        rewriter=QueryRewriter(adapters.chat, reasoning=settings.reasoning),
        retrieve=RetrievePassages(
            adapters.index,
            adapters.embedder,
            adapters.reranker,
            use_generated_questions=settings.use_generated_questions,
            use_table_rows=settings.use_table_rows,
        ),
        drafter=AnswerDrafter(adapters.chat, reasoning=settings.reasoning),
        evidence=EvidenceValidation(
            adapters.index,
            verifier,
            min_similarity=settings.min_similarity,
            grounding_check=settings.grounding_check,
            whole_word_acronyms=settings.whole_word_acronyms,
        ),
        advise=AdviseOnTerms(adapters.index, adapters.glossary),
        index=adapters.index,
        chat=adapters.chat,
        policy=AnsweringPolicy(
            extracts=settings.extracts,
            retry_extracts=settings.retry_extracts,
            fallback_model=settings.fallback_model,
            quoted_style=settings.answer_style is AnswerStyle.QUOTES,
            detailed_headings=settings.use_table_rows,
            retry_with_reasoning=settings.retry_with_reasoning,
            context_window=settings.context_window,
            classified_publications=classified,
        ),
    )
    return DoctrineUseCases(
        ask=ask,
        lookup_glossary=LookupGlossary(adapters.glossary),
        explain_order=ExplainOrder(
            adapters.index, adapters.embedder, adapters.chat, classified_publications=classified
        ),
        index=adapters.index,
        classified_publications=classified,
    )
