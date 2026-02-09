import asyncio
from collections.abc import Mapping
from typing import Any, Optional, Literal, TypeVar
from typing import TYPE_CHECKING

from fast_validation import ValidationRuleException, Schema
from pydantic import ValidationError, BaseModel, Field
from quart import request, has_request_context, g

from fast_app.exceptions.common_exceptions import AppException
from fast_app.exceptions.http_exceptions import UnprocessableEntityException
from fast_app.utils.api_filters import parse_user_filter
from fast_app.utils.api_utils import is_list_type, collect_list_values
from fast_app.utils.model_utils import build_search_query_from_string

if TYPE_CHECKING:
    pass


if TYPE_CHECKING:
    from fast_app.contracts.model import Model
    from fast_app.contracts.resource import Resource

S = TypeVar("S", bound=BaseModel)
FilterInput = BaseModel | Mapping[str, Any]


def _normalize_filter(filter_input: FilterInput | None) -> dict[str, Any]:
    if filter_input is None:
        return {}
    if isinstance(filter_input, BaseModel):
        return filter_input.model_dump(exclude_unset=True)
    if isinstance(filter_input, Mapping):
        return dict(filter_input)
    raise TypeError("filter must be a mapping or a Pydantic model.")

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

def get_bearer_token() -> str | None:
    """Get the token from the request.
    
    Returns:
        The token.

    Raises:
        UnauthorizedException: If the request is not authenticated.
        AppException: If the request does not have request context.
    """
    if has_request_context():
        # It's an HTTP request
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]  # Get the token part of the header
        return None
    else:
        raise AppException("Does not have request context.")

class ListQuery(Schema):
    """
    Common pagination and search query parameters.

    Designed for validating typical list endpoints.
    """

    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1)
    sort_by: Optional[str] = Field(None)
    sort_direction: Optional[Literal["asc", "desc"]] = Field(None)


class SearchQuery(ListQuery):
    search: str = Field(...)


def _build_sort_query(list_query: ListQuery, default_sort: Optional[list[tuple[str, int]]] = None) -> list[tuple[str, int]]:
    # User requested sort
    if list_query.sort_by and list_query.sort_direction:
        return [(list_query.sort_by, 1 if list_query.sort_direction == "asc" else -1)]
    
    # Sort modified internally
    if default_sort is not None:
        return default_sort
    
    # Fallback sort
    return [('_id', -1)]


async def search_paginated(model: type['Model'], resource: type['Resource'], *, filter: FilterInput | None = None, sort: Optional[list[tuple[str, int]]] = None) -> dict:
    base_filter = _normalize_filter(filter)

    params = await validate_query(SearchQuery)

    search_filter = build_search_query_from_string(params.search, model.all_fields())
    if base_filter:
        search_filter = {"$and": [base_filter, search_filter]}

    sort = _build_sort_query(params, sort)
    skip = (params.page - 1) * params.per_page
    res = await model.search(search_filter, params.per_page, skip, sort=sort)

    return {
        "meta": res["meta"],
        "data": await resource(res["data"]).dump(),
    }

async def list_paginated(model: type['Model'], resource: type['Resource'], *, filter: FilterInput | None = None, sort: Optional[list[tuple[str, int]]] = None) -> dict:
    base_filter = _normalize_filter(filter)

    params = await validate_query(ListQuery)
    
    sort = _build_sort_query(params, sort)
    skip = (params.page - 1) * params.per_page

    # Get total records and results at once
    total_records, result = await asyncio.gather(
        model.count(base_filter),
        model.find(base_filter, limit=params.per_page, skip=skip, sort=sort),
    )

    return {
        'meta': {
            'displaying': len(result),
            'skip': skip,
            'current_page': params.page,
            'per_page': params.per_page,
            'last_page': total_records // params.per_page + (1 if total_records % params.per_page else 0),
            'total': total_records,
        },
        'data': await resource(result).dump(),
    }

async def paginate(model: type['Model'], resource: type['Resource'], *, filter: FilterInput | None = None, sort: Optional[list[tuple[str, int]]] = None) -> dict:
    if request.args.get('search'):
        return await search_paginated(model, resource, filter=filter, sort=sort)
    else:
        return await list_paginated(model, resource, filter=filter, sort=sort)

def _sanitize_pydantic_errors(errors: list[dict]) -> list[dict]:
    """Return a minimal, JSON-safe error payload.

    Keeps only keys that are safe and useful for clients: loc, msg, type.
    Drops potentially sensitive or non-serialisable fields such as ctx/input/url.
    """
    sanitized: list[dict] = []
    for err in errors:
        sanitized.append({
            k: v
            for k, v in err.items()
            if k in ("loc", "msg", "type")
        })
    return sanitized

async def validate_request(schema: type[S], *, partial: bool = False) -> S:
    """
    Validate the request body against the schema. 
    Stores the validated _dictionary_ in `g.validated`.

    Args:
        schema: The schema to validate the request body against.
        partial: Whether to exclude unset fields from the validated data.

    Returns:
        The validated schema .

    Raises:
        UnprocessableEntityException: If the request body is invalid.
    """
    json_data = await request.get_json()
    try:
        instance = schema(**(json_data if json_data is not None else {}))
    except ValidationError as e:
        # Only catch pydantic parsing here
        raise UnprocessableEntityException(
            error_type="invalid_request",
            message="Request body validation failed.",
            data=_sanitize_pydantic_errors(e.errors()),
        )

    # Optional post-parse rule validation if the schema supports it (Schema class from fast-validation)
    if isinstance(instance, Schema):
        validate = getattr(instance, "validate", None)
        if callable(validate):
            try:
                await validate(partial=partial)
            except ValidationRuleException as exc:
                errors = exc.errors if exc.errors is not None else [{
                    "loc": list(exc.loc),
                    "msg": exc.message,
                    "type": exc.error_type,
                }]
                raise UnprocessableEntityException(
                    error_type="invalid_request",
                    message="Request body validation failed.",
                    data=errors,
                )

    validated = instance.model_dump(exclude_unset=partial)
    g.validated = validated
    return instance

def get_query(schema: type[BaseModel]) -> dict:
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

async def validate_query(schema: type[S], *, partial: bool = False) -> S:
    """
    Validate the request query parameters against the schema. 
    Stores the validated dictionary in `g.validated_query`

    Args:
        schema: The schema to validate the query parameters against.
        partial: Whether to exclude unset fields from the validated data.

    Returns:
        The validated data.

    Raises:
        UnprocessableEntityException: If the query parameters are invalid.
    """
    query_data = get_query(schema)
    try:
        instance = schema(**query_data)
    except ValidationError as e:
        raise UnprocessableEntityException(
            error_type="invalid_query",
            message="Query parameter validation failed.",
            data=_sanitize_pydantic_errors(e.errors()),
        )

    # Optional post-parse rule validation for query schemas as well (Schema class from fast-validation)
    if isinstance(instance, Schema):
        validate = getattr(instance, "validate", None)
        if callable(validate):
            try:
                await validate(partial=partial)
            except ValidationRuleException as exc:
                errors = exc.errors if exc.errors is not None else [{
                    "loc": list(exc.loc),
                    "msg": exc.message,
                    "type": exc.error_type,
                }]
                raise UnprocessableEntityException(
                    error_type="invalid_query",
                    message="Query parameter validation failed.",
                    data=errors,
                )

    validated = instance.model_dump(exclude_unset=partial)
    g.validated_query = validated
    return instance

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
        raise UnprocessableEntityException(
            error_type="invalid_query",
            message=f"Invalid filter in query parameter '{param_name}'.",
        )
