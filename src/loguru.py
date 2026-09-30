"""
Compatibility shim for loguru.

Provides seamless fallback to standard logging when loguru is not installed,
while delegating to real loguru when it is installed in site-packages.
"""

import logging
import os
import sys
import importlib.util

# Check if real loguru exists elsewhere in sys.path
_real_loguru = None
for _p in sys.path:
    # Skip our own directory
    if os.path.abspath(_p) == os.path.abspath(os.path.dirname(__file__)):
        continue
    _candidate = os.path.join(_p, "loguru")
    if os.path.isdir(_candidate) and os.path.isfile(os.path.join(_candidate, "__init__.py")):
        try:
            _spec = importlib.util.spec_from_file_location("loguru_pkg", os.path.join(_candidate, "__init__.py"))
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _real_loguru = _mod
                break
        except Exception:
            pass

if _real_loguru is not None:
    logger = _real_loguru.logger
else:
    class _LoguruFallback:
        def __init__(self):
            self._logger = logging.getLogger("voice_assistant")
            self._logger.setLevel(logging.INFO)
            if not self._logger.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(
                    logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s")
                )
                self._logger.addHandler(handler)
            self._handlers = {}
            self._handler_id = 1

        def debug(self, msg, *args, **kwargs):
            self._logger.debug(str(msg), *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            self._logger.info(str(msg), *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            self._logger.warning(str(msg), *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            self._logger.error(str(msg), *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            self._logger.critical(str(msg), *args, **kwargs)

        def exception(self, msg, *args, **kwargs):
            self._logger.exception(str(msg), *args, **kwargs)

        def success(self, msg, *args, **kwargs):
            self._logger.info(f"SUCCESS: {msg}", *args, **kwargs)

        def trace(self, msg, *args, **kwargs):
            self._logger.debug(f"TRACE: {msg}", *args, **kwargs)

        def remove(self, handler_id=None):
            if handler_id is None:
                self._logger.handlers.clear()
            elif handler_id in self._handlers:
                self._logger.removeHandler(self._handlers.pop(handler_id))

        def add(self, sink, level="INFO", format=None, rotation=None, retention=None, **kwargs):
            numeric_level = getattr(logging, level.upper(), logging.INFO) if isinstance(level, str) else level
            self._logger.setLevel(min(self._logger.level, numeric_level))
            
            if sink is sys.stderr or sink is sys.stdout:
                handler = logging.StreamHandler(sink)
            elif isinstance(sink, (str, os.PathLike)):
                os.makedirs(os.path.dirname(os.path.abspath(sink)), exist_ok=True)
                handler = logging.FileHandler(sink, encoding="utf-8")
            else:
                handler = logging.StreamHandler(sys.stderr)

            handler.setLevel(numeric_level)
            formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

            hid = self._handler_id
            self._handlers[hid] = handler
            self._handler_id += 1
            return hid

        def bind(self, **kwargs):
            return self

        def opt(self, **kwargs):
            return self

    logger = _LoguruFallback()

__all__ = ["logger"]
