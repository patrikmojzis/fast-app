import pytest

from fast_app import Event, EventListener
from fast_app.application import Application
from fast_app.core.events import dispatch_now


@pytest.mark.asyncio
async def test_dispatch_event():
    class Ping(Event):
        pass

    class Ponger(EventListener):
        called = False
        async def handle(self):
            Ponger.called = True

    app = Application()
    app.configure_events({Ping: [Ponger]})

    await dispatch_now(Ping())
    assert Ponger.called
    app.reset()
