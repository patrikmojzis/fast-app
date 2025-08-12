from typing import TYPE_CHECKING

from fast_app import Resource

if TYPE_CHECKING:
    from fast_app import Model


class NewClass(Resource):
    async def to_dict(self, data: 'Model') -> dict:
        return data.dict()
