"""Interpréteur de signaux MTP déterministe et notation sur le jeu de test."""

from hannibal_core.signals.interpreter import KB, compact, interpret
from hannibal_core.signals.scoring import score_interpretation

__all__ = ["KB", "compact", "interpret", "score_interpretation"]
