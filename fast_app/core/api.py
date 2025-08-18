import asyncio
from typing import Optional, Literal
from typing import TYPE_CHECKING

from pydantic import ValidationError, BaseModel, Field
from quart import request, has_request_context, has_websocket_context, websocket, jsonify, g

from fast_app.exceptions.common_exceptions import AppException
from fast_validation import ValidationRuleException, Schema
from fast_app.exceptions.http_exceptions import UnprocessableEntityException
from fast_app.utils.api_filters import parse_user_filter
from fast_app.utils.api_utils import is_list_type, collect_list_values
from fast_app.utils.model_utils import build_search_query_from_string

if TYPE_CHECKING:
    from quart import Response


if TYPE_CHECKING:
    from fast_app.contracts.model import Model
    from fast_app.contracts.resource import Resource
    from pydantic import BaseModel

def get_client_ip() -> str:
    """Get the client IP address from the request.
    
    If using reverse proxy like nginx update config to include the following:
    ```
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Real-IP $remote_addr;
    ```
    """
    # Try to get IP from X-Forwarded-For header first (for proxy cases)
    if 'X-Forwarded-For' in request.headers:
        ip = request.headers['X-Forwarded-For'].split(',')[0]
    # Then try X-Real-IP header
    elif 'X-Real-IP' in request.headers:
        ip = request.headers['X-Real-IP']
    # Finally fall back to remote address
    else:
        ip = request.remote_addr
    return ip

def get_bearer_auth_token() -> str | None:
    """Get the token from the request.
    
    Returns:
        The token.

    Raises:
        UnauthorisedException: If the request is not authenticated.
        AppException: If the request does not have request context.
    """
    if has_request_context():
        # It's an HTTP request
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]  # Get the token part of the header
        else:
            # Fallback to checking the query parameters if no Authorization header or not a Bearer token
            return request.args.get('token')
    else:
        raise AppException("Does not have request context.")


def get_websocket_auth_token() -> str | None:
    """Get the token from the websocket query string.

    Returns:
        The token if present in the `token` query parameter, otherwise None.

    Raises:
        UnauthorisedException: If there is no active websocket context.
        AppException: If the request does not have websocket context.
    """
    if not has_websocket_context():
        raise AppException("Does not have websocket context.")

    # Query string is bytes (e.g. b"token=abc&foo=bar"). Decode and parse.
    query = websocket.query_string.decode("utf-8") if websocket.query_string else ""
    if not query:
        return None

    params = {}
    for part in query.split("&"):
        if not part:
            continue
        key_value = part.split("=", 1)
        if len(key_value) == 2:
            key, value = key_value
            params[key] = value
    return params.get("token")


def get_request_auth_token() -> str | None:
    """Return auth token for the current context (HTTP or WebSocket).

    - If in HTTP request context, prefer Authorization: Bearer, then fallback to query param `token`.
    - If in WebSocket context, read query param `token` from the connection string.

    Returns None if token is not present. Raises if no applicable context.
    """
    if has_request_context():
        return get_bearer_auth_token()
    if has_websocket_context():
        return get_websocket_auth_token()
    raise AppException("Does not have request or websocket context.")

class PaginationQuery(BaseModel):
    """Common pagination and search query parameters.

    Designed for validating typical list endpoints.
    """

    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1)
    search: Optional[str] = Field(None)
    sort_by: Optional[str] = Field(None)
    sort_direction: Optional[Literal["asc", "desc"]] = Field(None)


async def search_paginated(model: 'Model', resource: 'Resource', *, query_param: dict | None = None) -> 'Response':
    if query_param is None:
        query_param = {}

    params = await validate_query(PaginationQuery)
    page = params["page"]
    per_page = params["per_page"]
    search = params.get("search")
    sort_by = params.get("sort_by")
    sort_direction = params.get("sort_direction")

    # Build sort query
    if sort_by and sort_direction:
        sort = [(sort_by, 1 if sort_direction == "asc" else -1)]  # user requested sort
    else:
        sort = g.get('sort', [('_id', -1)])  # sort modified internally or default sort

    search_filter = build_search_query_from_string(search, model.all_fields())
    if query_param:
        search_filter = {"$and": [query_param, search_filter]}

    res = await model.search(search_filter, per_page, (page - 1) * per_page, sort=sort)
    return jsonify({
        "meta": res["meta"],
        "data": await resource(res["data"]).dump(),
    })


async def list_paginated(model: 'Model', resource: 'Resource', *, query_param: dict | None = None) -> 'Response':
    if query_param is None:
        query_param = {}

    params = await validate_query(PaginationQuery)
    page = params["page"]
    per_page = params["per_page"]
    sort_by = params.get("sort_by")
    sort_direction = params.get("sort_direction")

    # Build sort query
    if sort_by and sort_direction:
        sort = [(sort_by, 1 if sort_direction == "asc" else -1)]  # user requested sort
    else:
        sort = g.get('sort', [('_id', -1)])  # sort modified internally or default sort

    # Get total records and results at once
    total_records, result = await asyncio.gather(
        model.count(query_param),
        model.find(query_param, limit=per_page, skip=(page - 1) * per_page, sort=sort),
    )

    total_pages = total_records // per_page + (1 if total_records % per_page else 0)

    return jsonify({
        'meta': {
            'current_page': page,
            'per_page': per_page,
            'last_page': total_pages,
            'total': total_records,
        },
        'data': await resource(result).dump(),
    })

async def validate_request(schema: BaseModel | object, *, exclude_unset: bool = False):
    """Validate the request body against the schema.

    Args:
        schema: The schema to validate the request body against.
        exclude_unset: Whether to exclude unset fields from the validated data.

    Returns:
        The validated data.

    Raises:
        UnprocessableEntityException: If the request body is invalid.
    """
    json_data = await request.get_json()
    try:
        instance = schema(**json_data)
    except ValidationError as e:
        # Only catch pydantic parsing here
        raise UnprocessableEntityException(error_type="invalid_request", data=e.errors())

    # Optional post-parse rule validation if the schema supports it (Schema class from fast-validation)
    if isinstance(instance, Schema):
        validate = getattr(instance, "validate", None)
        if callable(validate):
            try:
                await validate(partial=exclude_unset)
            except ValidationRuleException as exc:
                errors = exc.errors if exc.errors is not None else [{
                    "loc": list(exc.loc),
                    "msg": exc.message,
                    "type": exc.error_type,
                }]
                raise UnprocessableEntityException(error_type="invalid_request", data=errors)

    g.validated = instance.model_dump(exclude_unset=exclude_unset)

def get_query(schema: 'BaseModel') -> dict:
    """Extract query params tailored to a Pydantic schema without validating.

    - For List[...] fields, collect multiple values using getlist and key[] styles,
      and split comma-separated items when present.
    - For scalar fields, take the first value if present.
    - Leave type coercion to Pydantic in the subsequent validation step.
    """
    query_data: dict = {}
    for field_name, field in schema.model_fields.items():
        annotation = field.annotation
        if is_list_type(annotation):
            values = collect_list_values(field_name)
            if values:
                query_data[field_name] = values
        else:
            if field_name in request.args:
                query_data[field_name] = request.args.get(field_name)
            elif f"{field_name}[]" in request.args:
                # If client sent array syntax for a scalar field, keep the first one
                list_values = request.args.getlist(f"{field_name}[]")
                if list_values:
                    query_data[field_name] = list_values[0]
    return query_data

async def validate_query(schema: BaseModel | object, *, exclude_unset: bool = False):
    """Validate the request query parameters against the schema.
    
    Stores the validated dictionary in `g.validated_query` and returns it.
    """
    query_data = get_query(schema)
    try:
        instance = schema(**query_data)
    except ValidationError as e:
        raise UnprocessableEntityException(error_type="invalid_query", data=e.errors())

    # Optional post-parse rule validation for query schemas as well (Schema class from fast-validation)
    if isinstance(instance, Schema):
        validate = getattr(instance, "validate", None)
        if callable(validate):
            try:
                await validate(partial=exclude_unset)
            except ValidationRuleException as exc:
                errors = exc.errors if exc.errors is not None else [{
                    "loc": list(exc.loc),
                    "msg": exc.message,
                    "type": exc.error_type,
                }]
                raise UnprocessableEntityException(error_type="invalid_query", data=errors)

    validated = instance.model_dump(exclude_unset=exclude_unset)
    g.validated_query = validated
    return validated


def get_mongo_filter_from_query(
    *,
    param_name: str = "filter",
    allowed_fields: list[str] | None = None,
    allowed_ops: list[str] | None = None,
) -> dict:
    """Parse a JSON (or base64-JSON) filter from the query string safely.

    Accepts any nested Mongo-like structure, but enforces operator and field
    allowlists to prevent unsafe queries.

    Args:
        param_name: Query parameter name that carries the filter (default: "filter").
        allowed_fields: Optional list of allowed field paths (top-level allows dotted subpaths).
        allowed_ops: Optional list of allowed operators (defaults to a safe subset).

    Returns:
        A sanitized dictionary representing the Mongo filter.

    Raises:
        UnprocessableEntityException: If the filter is invalid or uses disallowed fields/ops.
    """

    raw = request.args.get(param_name)
    try:
        return parse_user_filter(
            raw=raw,
            allowed_fields=set(allowed_fields) if allowed_fields else None,
            allowed_ops=set(allowed_ops) if allowed_ops else None,
        )
    except ValueError as exc:
        raise UnprocessableEntityException(error_type="invalid_query", message=str(exc))