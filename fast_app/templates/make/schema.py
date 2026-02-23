from fast_validation import from_schema

from fast_app import Schema


class NewClass(Schema):
    pass


@from_schema(NewClass, partial=True)
class NewPartialClass(Schema):
    pass
