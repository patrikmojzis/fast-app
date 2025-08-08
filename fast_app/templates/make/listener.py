from fast_app.event_listener_base import EventListener


class Listener(EventListener):

    async def handle(self) -> None:
       # access event data from self.event
       pass