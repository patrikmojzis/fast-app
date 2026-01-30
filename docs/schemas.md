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

## Convenience field types

When I need quick coercion helpers, `fast_app.core.pydantic_types` ships a handful of annotated types that feel native to Pydantic while keeping Mongo- and JSON-friendly behaviour:

- `ObjectIdField`: Accepts strings or `ObjectId` instances and serialises back to hex strings.
- `DateField` and `DateTimeField`: Parse ISO strings (and datetimes with `Z`) into Python `date` / `datetime`, serialising back to ISO format.
- `IntFromStrField`: Coerces numeric strings and exact floats to integers, rejecting booleans and fractional floats.
- `JSONField`: Allows raw dict/list input or JSON strings and returns Python objects.
- `ShortStr`: Strips whitespace and constrains length to 1–255 characters.

```python
from fast_app.core.pydantic_types import (
    ObjectIdField,
    DateField,
    DateTimeField,
    IntFromStrField,
    ShortStr,
)


class SubscriptionSchema(Schema):
    user_id: ObjectIdField
    plan: ShortStr
    quota: IntFromStrField = 0
    starts_at: DateField
    renewed_at: DateTimeField | None = None

```

All of these types are plain Pydantic annotations, so they work with validators, JSON schema generation, and the automatic serialisation behaviour provided by FastApp resources.

## Async rule validation

After Pydantic validates structure and types, you can run additional async checks (e.g., hit the database, inspect related models). Define rules inside an inner `Meta` class using `Schema.Rule`.

```python
from typing import Optional, Literal
from pydantic import Field, EmailStr

from fast_app import Schema
from fast_app.core.pydantic_types import ObjectIdField
from fast_app.core.validation_rules.exists_validator_rule import ExistsValidatorRule
from app.models import Rep, County


class LeadSchema(Schema):
    name: Optional[str] = Field(None, description="Lead's full name")
    email: Optional[EmailStr] = Field(None, description="Lead's email")
    rep_id: Optional[ObjectIdField] = Field(None, description="Assigned sales representative")
    county_id: Optional[ObjectIdField] = Field(None, description="Lead county")
    source: Optional[Literal["direct", "eshop", "pharmacy", "distributor"]] = None

    class Meta:
        rules = [
            Schema.Rule("$.rep_id", [ExistsValidatorRule(allow_null=True)]),
            Schema.Rule("$.county_id", [ExistsValidatorRule(allow_null=True)]),
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

- `ExistsValidatorRule(model=None, *, field=None, db_key="_id", allow_null=False, is_object_id=True, each=False)` — verifies that IDs exist in the database. If `model` is omitted, the rule infers the model from the field name (e.g., `rep_id` → `Rep`). When `each=True`, every value in a list is checked.

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

