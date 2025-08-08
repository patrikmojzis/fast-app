from fast_app import Resource
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app import Model


class Resource(Resource):
    async def to_dict(self, data: 'Model') -> dict:
        return data.dict()
