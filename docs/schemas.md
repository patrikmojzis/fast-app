# Schemas

Schemas describe and validate incoming payloads. They are thin wrappers around Pydantic models with an additional async validation layer powered by `fast-validation`.

## Generating a schema

Scaffold a schema with the CLI. Naming convention mirrors controllers and routes.

```bash
fast-app make schema Lead
```

The generator creates `app/http_files/schemas/lead.py` containing a `LeadSchema` stub:

```python
from fast_app import Schema
from pydantic import Field


class LeadSchema(Schema):
    name: str = Field(..., max_length=120)
```

Keep schemas under `app/http_files/schemas/` so controllers and request handlers can import them easily.

## Pydantic-powered validation

Schemas inherit from `fast_validation.Schema`, a Pydantic `BaseModel` with sensible defaults (whitespace stripping, assignment validation, enum support). You can use the full range of Pydantic field types, constraints, and validators.

- Required vs optional fields (`Field(..., description="...")` vs `Field(None)`)
- Type hints for `EmailStr`, `constr`, `Literal`, `Annotated`, etc.
- Custom validators and field constraints, just like any Pydantic model.

Reference the Pydantic documentation for exhaustive options: [docs.pydantic.dev](https://docs.pydantic.dev/latest/).

```python
from pydantic import Field, EmailStr, constr

class InviteSchema(Schema):
    email: EmailStr
    name: constr(min_length=2, max_length=40)
    role: Literal["admin", "editor", "viewer"] = Field(..., description="Role in the workspace")
```

## Async rule validation

After Pydantic validates structure and types, you can run additional async checks (e.g., hit the database, inspect related models). Define rules inside an inner `Meta` class using `Schema.Rule`.

```python
from typing import Optional, Literal
from pydantic import Field, EmailStr

from fast_app import Schema
from fast_app.core.validation_rules.exists_validator_rule import ExistsValidatorRule
from app.models import Rep, County


class LeadSchema(Schema):
    name: Optional[str] = Field(None, description="Lead's full name")
    email: Optional[EmailStr] = Field(None, description="Lead's email")
    rep_id: Optional[str] = Field(None, description="Assigned sales representative")
    county_id: Optional[str] = Field(None, description="Lead county")
    source: Optional[Literal["direct", "eshop", "pharmacy", "distributor"]] = None

    class Meta:
        rules = [
            Schema.Rule("$.rep_id", [ExistsValidatorRule(Rep, allow_null=True)]),
            Schema.Rule("$.county_id", [ExistsValidatorRule(County, allow_null=True)]),
        ]
```

`Schema.Rule` accepts a JSONPath-like selector and a list of validator rules. Each rule receives the value, the whole payload, and a location tuple.

Run rule validation explicitly:

```python
payload = LeadSchema(**request.json)
await payload.validate()  # raises ValidationRuleException on failure
```

Framework helpers such as `fast_app.core.api.validate_request` call `await schema.validate()` for you, so most controllers only need to call the helper.

## Built-in rules

- `ExistsValidatorRule(model, *, db_key="_id", allow_null=False, is_object_id=True, each=False)` — verifies that IDs exist in the database. When `each=True`, every value in a list is checked.

To write your own rule, subclass `fast_validation.validation_rule.ValidatorRule`:

```python
from fast_validation import ValidatorRule, ValidationRuleException


class LongitudeRule(ValidatorRule):
    async def validate(self, *, value, data, loc):
        if value is None:
            return
        min_value, max_value = await make_db_call()
        if not (min_value <= float(value) <= max_value):
            raise ValidationRuleException("Longitude must be between -180 and 180", loc=tuple(loc))


class LocationSchema(Schema):
    longitude: float | None = None

    class Meta:
        rules = [Schema.Rule("$.longitude", [LongitudeRule()])]
```

Rules run sequentially for each matched value; collect errors are aggregated into a single `ValidationRuleException`.

## Tips

- Use `Field(..., alias="externalName")` when accepting camelCase payloads.
- Set `Field(default_factory=list)` for mutable defaults like tags or settings.
- Mark partial update schemas with optional fields and call `await schema.validate(partial=True)` to skip unset values.
- Keep schema modules small and reusable; share nested schemas (e.g., `LeadScheduleSchema`) across multiple resources.

With schemas, you get strict structural validation from Pydantic plus async rule checks for cross-cutting invariants.


