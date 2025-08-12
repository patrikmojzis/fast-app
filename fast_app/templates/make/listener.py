from fast_app import EventListener


class NewClass(EventListener):
    async def handle(self) -> None:
        # Access event data from self.event
        pass
