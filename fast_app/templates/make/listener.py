from fast_app import EventListener


class Listener(EventListener):

    async def handle(self) -> None:
       # access event data from self.event
       pass
