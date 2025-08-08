from typing import TYPE_CHECKING

from quart import request, has_request_context, jsonify, g
from fast_app.exceptions.http_exceptions import UnauthorisedException, UnprocessableEntityException
import asyncio
from pydantic import ValidationError, BaseModel, Field
from typing import Optional, Literal


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
        raise UnauthorisedException(error_type="missing_authorization_bearer_token")

class PaginationQuery(BaseModel):
    """Common pagination and search query parameters.

    Designed for validating typical list endpoints.
    """

    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1)
    search: Optional[str] = Field(None)
    sort_by: Optional[str] = Field(None)
    sort_direction: Optional[Literal["asc", "desc"]] = Field(None)


# TODO: refactor query and g.expand_query, used g.expand_query is used for passing filters from controller
async def paginate_all(model: 'Model', resource: 'Resource', *, query: dict = None):
    if query is None:
        query = {}

    params = validate_query(PaginationQuery)
    page = params["page"]
    per_page = params["per_page"]
    search = params.get("search")
    sort_by = params.get("sort_by")
    sort_direction = params.get("sort_direction")

    # Build sort query
    if sort_by and sort_direction:
        sort = [(sort_by, 1 if sort_direction == "asc" else -1)]  # user requested sort
    else:
        sort = g.get('sort', [('_id', -1)]) #  sort modified internally or default sort
        
    # Return search results if search is provided
    if search:
        res = await model.search(search, per_page, (page - 1) * per_page, sort=sort);
        return jsonify({
            "meta": res["meta"],
            "data": await resource(res["data"]).dump()
        })
        
    else:
        # Apply expand query if provided
        if g.get("expand_query"):
            query = {**query, **g.get("expand_query")}

        # Get total records and results at once
        total_records, result = await asyncio.gather(
            model.count(query),
            model.find(query, limit=per_page, skip=(page - 1) * per_page, sort=sort)
        )

        total_pages = total_records // per_page + (1 if total_records % per_page else 0)

        return jsonify({
            'meta': {
                'current_page': page,
                'per_page': per_page,
                'last_page': total_pages,
                'total': total_records,
            },
            'data': await resource(result).dump()
        })

async def validate_request(schema: 'BaseModel', *, exclude_unset: bool = False):
    """Validate the request body against the schema.

    Args:
        schema: The schema to validate the request body against.
        exclude_unset: Whether to exclude unset fields from the validated data.

    Returns:
        The validated data.

    Raises:
        UnprocessableEntityException: If the request body is invalid.
    """
    try:
        json_data = await request.get_json()
        validated = schema(**json_data).model_dump(exclude_unset=exclude_unset)
        g.validated = validated
    except ValidationError as e:
        raise UnprocessableEntityException(error_type="invalid_request", data=e.errors())

def validate_query(schema: 'BaseModel', *, exclude_unset: bool = False):
    """Validate the request query parameters against the schema.
    
    Stores the validated dictionary in `g.validated_query` and returns it.
    """
    try:
        # Convert MultiDict to a plain dict (first value wins per key)
        query_data = dict(request.args)
        validated = schema(**query_data).model_dump(exclude_unset=exclude_unset)
        g.validated_query = validated
        return validated
    except ValidationError as e:
        raise UnprocessableEntityException(error_type="invalid_query", data=e.errors())