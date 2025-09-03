from pydantic import ConfigDict
from fast_validation import Schema

from fast_app.core.pydantic_types import ObjectIdField, DateField, DateTimeField, JSONField


def test_model_json_schema_with_objectid_field():
    class MySchema(Schema):
        # Required due to using bson.ObjectId as the underlying type
        model_config = ConfigDict(arbitrary_types_allowed=True)

        id: ObjectIdField

    schema = MySchema.model_json_schema()
    props = schema.get("properties", {})
    assert "id" in props
    assert props["id"].get("type") == "string"
    assert props["id"].get("pattern") == "^[0-9a-fA-F]{24}$"



def test_model_json_schema_with_date_and_datetime_fields():
    class MySchema(Schema):
        birthday: DateField
        created_at: DateTimeField

    schema = MySchema.model_json_schema()
    props = schema.get("properties", {})

    assert "birthday" in props and props["birthday"].get("type") == "string"
    fmt_date = props["birthday"].get("format")
    if fmt_date is not None:
        assert fmt_date == "date"

    assert "created_at" in props and props["created_at"].get("type") == "string"
    fmt_dt = props["created_at"].get("format")
    if fmt_dt is not None:
        assert fmt_dt == "date-time"


def test_model_json_schema_with_json_field():
    class MySchema(Schema):
        payload: JSONField

    schema = MySchema.model_json_schema()
    props = schema.get("properties", {})
    assert "payload" in props

