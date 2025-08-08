"""
Pytest configuration and shared fixtures for FastApp tests.
"""

import pytest
from faker import Faker

fake = Faker()


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {
        "name": fake.name(),
        "email": fake.email(),
        "company": fake.company(),
    }


@pytest.fixture
def mock_database():
    """Mock database fixture for testing."""
    # This can be expanded when you set up actual database mocking
    pass


# Configure pytest-asyncio
pytest_plugins = ['pytest_asyncio']