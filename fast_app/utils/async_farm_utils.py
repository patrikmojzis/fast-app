import asyncio
import time
from multiprocessing import Process
from typing import Optional
import json
import logging
from aio_pika import IncomingMessage
from dataclasses import dataclass

class AckGuard:
    def __init__(self, message: IncomingMessage):
        self.message = message
        self.acked: bool = False

    async def ack(self) -> None:
        if self.acked:
            return

        await self.message.ack()
        self.acked = True


async def await_processes_death(processes: list[Process], grace_s: int = 2) -> None:
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline and any(p.is_alive() for p in processes):
        await asyncio.sleep(0.2)

def decode_message(body: bytes) -> Optional[dict]:
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        logging.warning("[decode_message] Invalid message body", body.decode("utf-8"))
        return None