"""Tiny in-process event bus: the call pipeline emits, the web page listens over SSE."""

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self):
        self.history: dict[str, list] = defaultdict(list)
        self.queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def emit(self, session_id: str, kind: str, data):
        event = {"kind": kind, "data": data}
        self.history[session_id].append(event)
        for q in self.queues[session_id]:
            q.put_nowait(event)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for event in self.history[session_id]:
            q.put_nowait(event)
        self.queues[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue):
        if q in self.queues[session_id]:
            self.queues[session_id].remove(q)


bus = EventBus()
