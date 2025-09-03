import factory

# Adjust import to your target model
from app.models.model import Model


class NewClass(factory.Factory):
    class Meta:
        model = Model

    # Define default attributes here
    # example_field = factory.Faker('name')


