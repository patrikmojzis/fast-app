from typing import TYPE_CHECKING

from fast_app.contracts.factory import Factory

# Adjust import to your target model
if TYPE_CHECKING:  # pragma: no cover - template typing aid
    from app.models.model import Model


class NewClassFactory(Factory['Model']):

    # Define default attributes here
    # example_field = Faker("name")
    # constant_field = Value("Always the same")
    # computed_field = Function(lambda: "value")
    ...
