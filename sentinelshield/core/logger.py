import logging
import os
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# System logger
system_log_path = 'logs/system.log'
system_handler = RotatingFileHandler(system_log_path, maxBytes=5_000_000, backupCount=3)
system_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
system_handler.setFormatter(system_formatter)
system_logger = logging.getLogger('sentinelshield.system')
system_logger.setLevel(logging.INFO)
system_logger.addHandler(system_handler)

# API logger
api_log_path = 'logs/api.log'
api_handler = RotatingFileHandler(api_log_path, maxBytes=5_000_000, backupCount=3)
api_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
api_handler.setFormatter(api_formatter)
api_logger = logging.getLogger('sentinelshield.api')
api_logger.setLevel(logging.INFO)
api_logger.addHandler(api_handler)

# Default logger for backward compatibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinelshield")
