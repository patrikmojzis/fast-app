# Controllers

Controllers orchestrate request handling: validate payloads, invoke domain logic, and return resources. Because FastApp leans on dependency injection for route parameters, controllers can stay thin and focused.

## Typical layout

Place controllers under `app/http_files/controllers/`.

Controllers are regular Python modules exporting async functions. Combine them with schemas, models, and resources for a clean flow.

```python
from typing import Literal

from fast_app import Schema, ExistsValidatorRule, paginate
from fast_app.core.pydantic_types import ObjectIdField
from quart import g
from pydantic import Field

from app.http_files.resources.lead_resource import LeadResource
from app.http_files.schemas.lead_schema import LeadSchema
from app.models.lead import Lead
from app.models.rep import Rep
from app.models.county import County

async def index():
    return await paginate(Lead, LeadResource)


async def show(lead: Lead):
    return LeadResource(lead)


async def store(data: LeadSchema):
    lead = await Lead.create(g.validated)
    return LeadResource(lead)


async def update(lead: Lead, data: LeadSchema):
    await lead.update(g.validated)
    return LeadResource(lead)


async def destroy(lead: Lead):
    await lead.delete()
```

## Patterns for larger controllers

- **Services**: move complex business logic into `app/http_files/services` or domain modules; keep controllers as coordinators.

Controllers are intentionally lightweight: they accept validated inputs, call domain services, and wrap outputs. With schemas and resources handling validation and presentation, controllers stay easy to read and test.


