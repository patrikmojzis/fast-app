from typing import Optional, TYPE_CHECKING

from bson import ObjectId
from quart import jsonify, g, request

from fast_app.core.api import list_paginated, search_paginated, validate_request
from fast_app.core.middlewares import EtagMiddleware
from fast_app.decorators.middleware_decorator import middleware
from fast_app.exceptions.http_exceptions import UnprocessableEntityException, UnauthorisedException

if TYPE_CHECKING:
    from fast_app.model_base import Model
    from fast_app.contracts.resource import Resource
    from pydantic import BaseModel


async def _get_model_by_id(id: str, Model: 'Model'):
    if not ObjectId.is_valid(id):
        raise UnprocessableEntityException(error_type="invalid_object_id", message=f"`{id}` is not a valid ObjectId")

    return await Model.find_by_id_or_fail(id)

async def authorise(target, ability: Optional[str] = None):
    """
    Authorize the current user to perform an action.
    
    Args:
        target: Policy function, model instance, or model class
        ability: Ability name (required when target is model instance/class)
    """
    user = g.get("user")
    if not user:
        raise UnauthorisedException()
    
    await user.authorize(target, ability)

@middleware(EtagMiddleware)
async def simple_show(id: str, Model: 'Model', Resource: 'Resource', ability: Optional[str] = None):
    res = await _get_model_by_id(id, Model)
    if ability:
        await authorise(res, ability)
    return await Resource(res).to_response()

@middleware(EtagMiddleware)
async def simple_index(Model: 'Model', Resource: 'Resource', extended_query: dict | None = None):
    if request.args.get("search"):
        return await search_paginated(Model, resource=Resource, query_param=extended_query)
    return await list_paginated(Model, resource=Resource, query_param=extended_query)

@middleware(EtagMiddleware)
async def simple_store(Model: 'Model', Resource: 'Resource', Schema: 'BaseModel'):
    await validate_request(Schema)
    data = g.get("validated")
    res = await Model.create(data)
    return await Resource(res).to_response()

@middleware(EtagMiddleware)
async def simple_update(id: str, Model: 'Model', Resource: 'Resource', Schema: 'BaseModel', ability: Optional[str] = None):
    res = await _get_model_by_id(id, Model)
    if ability:
        await authorise(res, ability)
    await validate_request(Schema, exclude_unset=True)
    await res.update(g.get("validated"))
    return await Resource(res).to_response()


async def simple_destroy(id: str, Model: 'Model', ability: Optional[str] = None):
    res = await _get_model_by_id(id, Model)
    if ability:
        await authorise(res, ability)
    await res.delete()
    return jsonify({"message": "Resource deleted."})