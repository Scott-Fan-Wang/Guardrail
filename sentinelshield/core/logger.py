import logging
import os
import queue
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener

_FILE_LOGGING_DISABLED = os.environ.get('DISABLE_FILE_LOGGING', '').lower() in ('1', 'true', 'yes')

# Ensure logs directory exists
if not _FILE_LOGGING_DISABLED:
    os.makedirs('logs', exist_ok=True)

system_log_path = 'logs/system.log'
api_log_path = 'logs/api.log'

_log_queue: queue.Queue = queue.Queue(-1)
_listener: QueueListener | None = None


def _ensure_listener_started() -> QueueListener | None:
    global _listener
    if _FILE_LOGGING_DISABLED:
        return None
    if _listener is not None:
        return _listener

    system_handler = RotatingFileHandler(system_log_path, maxBytes=5_000_000, backupCount=3)
    api_handler = RotatingFileHandler(api_log_path, maxBytes=5_000_000, backupCount=3)

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    system_handler.setFormatter(formatter)
    api_handler.setFormatter(formatter)

    _listener = QueueListener(_log_queue, system_handler, api_handler, respect_handler_level=True)
    _listener.start()
    return _listener


def stop_logging() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


_ensure_listener_started()

# System logger (async)
system_logger = logging.getLogger('sentinelshield.system')
system_logger.setLevel(logging.INFO)
system_logger.propagate = False
if not _FILE_LOGGING_DISABLED and not any(isinstance(h, QueueHandler) for h in system_logger.handlers):
    system_logger.addHandler(QueueHandler(_log_queue))

# API logger (async)
api_logger = logging.getLogger('sentinelshield.api')
api_logger.setLevel(logging.INFO)
api_logger.propagate = False
if not _FILE_LOGGING_DISABLED and not any(isinstance(h, QueueHandler) for h in api_logger.handlers):
    api_logger.addHandler(QueueHandler(_log_queue))

# Default logger for backward compatibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinelshield")
