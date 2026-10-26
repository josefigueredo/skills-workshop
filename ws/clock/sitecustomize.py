"""Capture only (ws/capture.py puts this folder on a real step's PYTHONPATH): Python's clock starts at WS_CLOCK.

Every process starts at the episode's moment and moves forward with real time, so a rerun prints the same times and
waits or timeouts still work. Python imports sitecustomize before anything else, so `now=time.time` defaults bind to
this clock too. It covers time.time, time.time_ns, the no-argument localtime/gmtime/ctime/strftime and
datetime.now/today; not other languages."""
import datetime
import os
import time

_start = float(os.environ.get("WS_CLOCK", "0"))
if _start:
    _mono, _mono_ns = time.monotonic(), time.monotonic_ns()
    _localtime, _gmtime, _ctime, _strftime = time.localtime, time.gmtime, time.ctime, time.strftime

    def _now() -> float:
        return _start + (time.monotonic() - _mono)

    time.time = _now
    time.time_ns = lambda: int(_start * 1e9) + (time.monotonic_ns() - _mono_ns)
    time.localtime = lambda secs=None: _localtime(_now() if secs is None else secs)
    time.gmtime = lambda secs=None: _gmtime(_now() if secs is None else secs)
    time.ctime = lambda secs=None: _ctime(_now() if secs is None else secs)
    time.strftime = lambda fmt, t=None: _strftime(fmt, time.localtime() if t is None else t)

    class _DateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(_now(), tz)

        @classmethod
        def today(cls):
            return cls.fromtimestamp(_now())

        @classmethod
        def utcnow(cls):
            return cls.fromtimestamp(_now(), datetime.timezone.utc).replace(tzinfo=None)

    class _Date(datetime.date):
        @classmethod
        def today(cls):
            return cls.fromtimestamp(_now())

    datetime.datetime, datetime.date = _DateTime, _Date
