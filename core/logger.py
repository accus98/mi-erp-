import logging
import json
import sys
import os
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """
    Format logs as JSON objects for structured logging (Datadog/ELK ready).
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields (context)
        if hasattr(record, 'context'):
            log_record.update(record.context)
            
        return json.dumps(log_record)

def get_logger(name, level=logging.INFO):
    """
    Factory to return a configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding multiple handlers if get_logger is called repeatedly
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        # Check env for format preference
        log_format = os.getenv('LOG_FORMAT', 'json')
        
        if log_format.lower() == 'json':
            handler.setFormatter(JsonFormatter())
        else:
            # Human readable fallback
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            
        logger.addHandler(handler)
        
    return logger

# Default instance
logger = get_logger("nexo_erp")
