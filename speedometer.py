from contextvars import ContextVar, Token
from threading import Lock
from time import time
from typing import Optional

from tqdm import tqdm

_speedometer: ContextVar[Optional["Speedometer"]] = ContextVar(
    "_speedometer",
    default=None,
)


class Speedometer:
    _accumulated: int
    _last_refresh: float
    _lock: Lock
    _tqdm: tqdm
    _unit: str
    _token: Token[Optional["Speedometer"]]

    def __init__(self, tqdm: tqdm, unit: Optional[str] = None):
        self._accumulated = 0
        self._last_refresh = time()
        self._lock = Lock()
        self._tqdm = tqdm
        self._unit = unit or "items"

    @classmethod
    def increment(cls, value: int):
        if current := _speedometer.get():
            current._increment(value)

    def _increment(self, value: int):
        with self._lock:
            self._accumulated += value
        self._refresh_maybe()

    def _refresh_maybe(self):
        now = time()
        if now - self._last_refresh < 1 and self._accumulated < 1000:
            return
        self._report(now)
        with self._lock:
            self._accumulated = 0
            self._last_refresh = now

    def _report(self, now: float):
        speed = float(self._accumulated) / (now - self._last_refresh)
        self._tqdm.postfix = f"({speed:.03f} {self._unit}/s)"

    def __enter__(self):
        self._token = _speedometer.set(self)
        return self

    def __exit__(self, *_):
        self._report(time())
        _speedometer.reset(self._token)
