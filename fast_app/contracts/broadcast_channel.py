from abc import ABC


class BroadcastChannel(ABC):
    """
    Base class for all broadcast channels.
    """
    
    def __init__(self, *args, **kwargs):
        pass

    async def get_channel_name(self, *args, **kwargs) -> str:
        """
        Get the name of the channel.
        """
        return self.__class__.__name__

    async def can_broadcast(self, *args, **kwargs) -> bool:
        """
        Check if the channel can broadcast the event.
        """
        return True

    async def can_listen(self, *args, **kwargs) -> bool:
        """
        Check if the channel can listen to the event.
        """
        return True