from fast_app.contracts.resource import Resource
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.model_base import Model


class Resource(Resource):
    async def to_dict(self, data: 'Model') -> dict:
        return data.dict()