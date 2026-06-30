import logging
import json
import sys
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "service_name": self.service_name,
            "level": record.levelname,
            "message": record.getMessage()
        }
        
        # If there are exception details, add them
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_payload)

def get_logger(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    # Check if handlers are already set up to avoid duplicate logging inside Docker
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter(service_name))
        logger.addHandler(handler)
        
    # Prevent propagation to the root logger to avoid standard text duplication
    logger.propagate = False
    
    return logger
