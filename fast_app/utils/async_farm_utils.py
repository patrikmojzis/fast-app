import asyncio
import time
from multiprocessing import Process

async def await_processes_death(processes: list[Process], grace_s: int = 2) -> None:
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline and any(p.is_alive() for p in processes):
        await asyncio.sleep(0.2)