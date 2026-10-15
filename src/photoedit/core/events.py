"""Change events (P7.8): the stores publish one after every successful write, so the UI can follow what the AI
(or another tab, or the CLI) changes.

Publishing never blocks: each subscription keeps a bounded queue, and a listener that falls behind loses the
oldest events and gets one ``resync`` event instead. The origin of a change (UI, AI, CLI) comes from a context
variable each front-end sets; jobs carry the origin of whoever started them into their threads.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from photoedit.models.events import ChangeEvent, EventKind, Origin

SUBSCRIPTION_LIMIT = 256

_origin: ContextVar[Origin] = ContextVar("photoedit_origin", default=Origin.UI)


def current_origin() -> Origin:
    return _origin.get()


@contextmanager
def origin(value: Origin) -> Iterator[None]:
    """Changes made inside this block are attributed to ``value``."""
    token = _origin.set(value)
    try:
        yield
    finally:
        _origin.reset(token)


def set_origin(value: Origin) -> None:
    """Attribute the rest of this context's changes to ``value`` (a front-end's entry point, e.g. the CLI)."""
    _origin.set(value)


class Subscription:
    def __init__(self, bus: EventBus, limit: int, notify: Callable[[], None] | None) -> None:
        self._bus = bus
        self._events: deque[ChangeEvent] = deque()
        self._limit = limit
        self._dropped = False
        self._notify = notify
        self._ready = threading.Condition()

    def drain(self) -> list[ChangeEvent]:
        """Everything since the last drain, oldest first; a ``resync`` first if events were dropped."""
        with self._ready:
            events = list(self._events)
            self._events.clear()
            dropped, self._dropped = self._dropped, False
        if dropped:
            events.insert(0, self._bus.resync_event())
        return events

    def wait(self, timeout: float) -> list[ChangeEvent]:
        """``drain()``, waiting up to ``timeout`` s for the first event (for threads; the API uses notify)."""
        with self._ready:
            self._ready.wait_for(lambda: self._events or self._dropped, timeout)
        return self.drain()

    def close(self) -> None:
        self._bus.unsubscribe(self)

    def _put(self, event: ChangeEvent) -> None:
        with self._ready:
            if len(self._events) >= self._limit:
                self._events.popleft()
                self._dropped = True
            self._events.append(event)
            self._ready.notify_all()
        if self._notify is not None:
            self._notify()


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = itertools.count(1)
        self._subscriptions: list[Subscription] = []

    def subscribe(
        self, *, limit: int = SUBSCRIPTION_LIMIT, notify: Callable[[], None] | None = None
    ) -> Subscription:
        """A new listener. ``notify`` is called (from the publishing thread) after each event is queued; it
        must not block."""
        subscription = Subscription(self, limit, notify)
        with self._lock:
            self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            if subscription in self._subscriptions:
                self._subscriptions.remove(subscription)

    def publish(
        self,
        kind: EventKind,
        ids: Iterable[str] = (),
        *,
        summary: str | None = None,
        source: Origin | None = None,
    ) -> ChangeEvent:
        """Tell every listener; ``source`` overrides the current origin (jobs use their starter's)."""
        with self._lock:
            event = ChangeEvent(
                seq=next(self._seq),
                kind=kind,
                ids=list(ids),
                origin=source or current_origin(),
                summary=summary,
            )
            listeners = list(self._subscriptions)
        for subscription in listeners:
            subscription._put(event)
        return event

    def resync_event(self) -> ChangeEvent:
        with self._lock:
            return ChangeEvent(seq=next(self._seq), kind=EventKind.RESYNC, origin=current_origin())
