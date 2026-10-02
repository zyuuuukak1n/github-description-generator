"""Secure logging configuration with sensitive data masking."""

import logging
import re
import sys
from typing import List


class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive tokens (e.g. GitHub PATs, API keys) in log records."""

    PATTERNS: List[re.Pattern] = [
        re.compile(r"(ghp_[A-Za-z0-9]{20,})"),
        re.compile(r"(github_pat_[A-Za-z0-9_]{30,})"),
        re.compile(r"(AIza[0-9A-Za-z-_]{35})"),  # Google API Key
        re.compile(r"(sk-[A-Za-z0-9-_]{20,})"),  # OpenAI Key
        re.compile(r"(Bearer\s+)[A-Za-z0-9-_.]+"),
        re.compile(r"(token\s*=\s*['\"])[^'\"]+(['\"])"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in self.PATTERNS:
                record.msg = pattern.sub(r"\1***MASKED***", record.msg)
        if record.args:
            # Mask sensitive info inside args if formatted
            if isinstance(record.args, dict):
                sanitized = {}
                sensitive_keys = ["token", "key", "secret", "password"]
                for k, v in record.args.items():
                    if any(s in k.lower() for s in sensitive_keys):
                        sanitized[k] = "***MASKED***"
                    else:
                        sanitized[k] = v
                record.args = sanitized
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup root application logger with formatting and security filtering."""
    logger = logging.getLogger("github_description_app")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    logger.addHandler(handler)
    logger.propagate = False
    return logger
