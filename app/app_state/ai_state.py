from PySide6.QtCore import QObject, Signal

from app.core.utils.app_logger import get_logger

_log = get_logger("ui.ai_state")


class AIState(QObject):
    """Manages AI panel reactive state via Qt signals.

    Emits signals when provider health changes, models are refreshed,
    AI settings are updated, streaming tokens arrive, responses complete,
    errors occur, or task runs finish. Consumers connect to these signals
    rather than polling or calling services directly.
    """

    health_changed = Signal(object)       # carries ProviderHealth
    models_refreshed = Signal(list)       # carries list[str]
    ai_settings_changed = Signal(object)  # carries AISettings
    token_received = Signal(object)       # carries StreamToken
    response_complete = Signal(object)    # carries AIResponse
    error_occurred = Signal(str)          # carries error message string
    task_complete = Signal(object)        # carries TaskRunResult

    def __init__(self, parent=None):
        super().__init__(parent)
