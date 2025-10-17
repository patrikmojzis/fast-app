# Middlewares

Fast App ships with a collection of route middleware that help you compose behaviour around your handlers. Each middleware is applied through the `@middleware` decorator and receives the fully-bound handler arguments. This section covers four core middlewares you are likely to use in production.

## AuthorizeMiddleware

Use `AuthorizeMiddleware` to check abilities before executing a handler. It delegates to the authenticated user's `authorize` method and supports either class-level or instance-level checks.

```python
@middleware(AuthorizeMiddleware("update", "post"))
async def update_post(post: Post):
    ...

@middleware(AuthorizeMiddleware("create", Post))
async def create_post():
    ...
```

- Resolves the referenced target either by name (from bound kwargs) or class.
- Raises `UnauthorisedException` when the user is missing or the policy denies.
- Ideal companion to `ModelBindingMiddleware` so instance checks receive the already-bound model.

## BelongsToMiddleware

`BelongsToMiddleware` ensures relational integrity between two bound models. It is particularly useful for nested resources where both parent and child models are injected into the handler.

```python
@middleware(BelongsToMiddleware("organisation_member", "organisation"))
async def show_invitation(
    organisation: Organisation,
    organisation_member: OrganisationMember,
):
    ...
```

- Verifies that the child model's foreign key matches the parent's identifier.
- Supports custom `foreign_key` and `parent_key` parameters when naming differs.
- Raises `NotFoundException` to avoid leaking the existence of other tenants' data.

## EtagMiddleware

`EtagMiddleware` adds HTTP caching semantics to JSON responses by computing a SHA1 digest of the serialised body and comparing it with the incoming `If-None-Match` header.

```python
@middleware(EtagMiddleware())
async def list_posts():
    return PostsResource(await Post.all())
```

- Returns `304 Not Modified` when the computed ETag matches the request header.
- Automatically sets the `ETag` response header on cacheable responses.
- Keeps handlers unchanged; simply wrap the existing route.

## ThrottleMiddleware

`ThrottleMiddleware` provides per-identity request limiting with a configurable window and request count.

```python
@middleware(ThrottleMiddleware(limit=60, window_seconds=60))
async def sensitive_action():
    ...
```

- Identifies clients via the authenticated user's id or, as a fallback, their IP address.
- Uses Redis-backed counters to track request volume.
- Raises `TooManyRequestsException` when the limit is exceeded, returning a `429` response.

Combine these middlewares as needed to layer authorisation, data protection, performance, and rate limiting policies on a per-route basis.

