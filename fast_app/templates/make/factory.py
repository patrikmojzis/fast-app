import factory

# Adjust import to your target model
from app.models.model import Model as TargetModel


class NewClass(factory.Factory):
    class Meta:
        model = TargetModel

    # Define default attributes here
    # example_field = factory.Faker('name')


