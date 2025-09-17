import asyncio
import os
import time
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RABBIT_INTEGRATION", "0") != "1",
    reason="Set RUN_RABBIT_INTEGRATION=1 to run RabbitMQ-backed integration test",
)


async def _emit_result(value: str, queue_name: str) -> None:
    """Async callable executed by worker: publishes value to a result queue."""
    import aio_pika

    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    conn = await aio_pika.connect_robust(url)
    try:
        chan = await conn.channel()
        q = await chan.declare_queue(queue_name, durable=False, auto_delete=True)
        await chan.default_exchange.publish(
            aio_pika.Message(body=value.encode("utf-8")), routing_key=q.name
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_queue_end_to_end_with_real_rabbitmq(monkeypatch, tmp_path):
    """
    Full-path test:
      - Start AsyncFarm supervisor with 1 worker
      - Enqueue an async callable via fast_app.core.queue.queue
      - Receive result on a dedicated RabbitMQ queue
    """
    # Isolate broker artifacts with unique names
    unique = uuid.uuid4().hex[:8]
    jobs_queue = f"af.jobs.{unique}"
    ctrl_ex = f"af.ctrl.{unique}"
    worker_ex = f"af.worker.{unique}"

    # Configure environment
    monkeypatch.setenv("PROJECT_ROOT", os.getcwd())  # ensure import of tests.* in workers
    monkeypatch.setenv("QUEUE_DRIVER", "async_farm")
    monkeypatch.setenv("ASYNC_FARM_JOBS_QUEUE", jobs_queue)
    monkeypatch.setenv("ASYNC_FARM_CONTROL_EXCHANGE", ctrl_ex)
    monkeypatch.setenv("ASYNC_FARM_WORKER_EXCHANGE", worker_ex)
    monkeypatch.setenv("MIN_WORKERS", "1")
    monkeypatch.setenv("MAX_WORKERS", "1")
    monkeypatch.setenv("PREFETCH_PER_WORKER", "10")

    # Verify broker reachable, else skip fast
    try:
        import aio_pika

        conn = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"))
        await conn.close()
    except Exception as e:  # pragma: no cover - environment dependent
        pytest.skip(f"RabbitMQ not reachable: {e}")

    # Start supervisor
    from fast_app.integrations.async_farm.supervisor import AsyncFarmSupervisor

    sup = AsyncFarmSupervisor()
    run_task = asyncio.create_task(sup.run())

    # Wait for worker to register heartbeat (workers dict gets populated)
    deadline = time.time() + 15
    while time.time() < deadline and len(sup.workers) == 0:
        await asyncio.sleep(0.2)
    assert len(sup.workers) >= 1, "Worker did not start in time"

    # Prepare result queue and consumer
    import aio_pika

    result_queue_name = f"af.results.{unique}"
    conn = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"))
    try:
        chan = await conn.channel()
        result_queue = await chan.declare_queue(result_queue_name, durable=False, auto_delete=True)

        # Enqueue real task via queue()
        from fast_app.core.queue import queue as queue_fn

        queue_fn(_emit_result, "hello", queue_name=result_queue_name)
        await asyncio.sleep(0)  # allow publisher task to schedule

        # Observe worker heartbeat active_tasks rising as a signal of job pickup
        pickup_deadline = time.time() + 10
        while time.time() < pickup_deadline:
            if any(int(st.get("active_tasks", 0)) > 0 for st in sup.workers.values()):
                break
            await asyncio.sleep(0.2)

        # Wait for result
        body: str | None = None
        async def wait_result():
            nonlocal body
            try:
                incoming = await result_queue.get(timeout=20)
                body = incoming.body.decode("utf-8")
                await incoming.ack()
            except Exception:
                pass

        await asyncio.wait_for(wait_result(), timeout=25)
        assert body == "hello"
    finally:
        await conn.close()

    # Shutdown supervisor and wait for clean exit
    sup.request_shutdown()
    await asyncio.wait_for(run_task, timeout=20)


