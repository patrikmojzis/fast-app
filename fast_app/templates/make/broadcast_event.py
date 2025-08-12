from typing import Union

from fast_app import BroadcastEvent

if False:
    # for typing only
    from fast_app import BroadcastChannel


class NewClass(BroadcastEvent):
    async def broadcast_on(self, *args, **kwargs) -> Union[str, 'BroadcastChannel']:
        return 'public'


