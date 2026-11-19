"""bge-reranker (sentence-transformers), chargé au démarrage du service, demi-précision sur GPU."""

from collections.abc import Sequence
from typing import Any

from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class CrossEncoderScorer:
    def __init__(
        self, model: str, *, device: str, half_precision: bool, batch_size: int, max_length: int
    ) -> None:
        self._model_name = model
        self._device = device
        self._half_precision = half_precision
        self._batch_size = batch_size
        self._max_length = max_length
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def load(self) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(self._model_name, device=self._device, max_length=self._max_length)
        if self._device.startswith("cuda") and self._half_precision:
            self._model.model.half()
        log.info("rerank_model_loaded", model=self._model_name, device=self._device)

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        if self._model is None:
            self.load()
        scores = self._model.predict(list(pairs), batch_size=self._batch_size, show_progress_bar=False)
        return [float(score) for score in scores]
