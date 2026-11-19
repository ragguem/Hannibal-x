import hashlib
from pathlib import Path

from hannibal_core.signals import KB

from hannibal_platform.logging import get_logger

log = get_logger(__name__)


def load_signal_table(path: Path | None) -> KB | None:
    """Table MTP tirée de la publication, hors dépôt. Sans chemin, seule la syntaxe simplifiée est lue."""
    if path is None:
        log.warning("signal_table_not_configured")
        return None
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    table = KB(path)
    log.info("signal_table_loaded", signals=len(table.signals), sha256=fingerprint)
    return table
