"""Pytest configuration and shared fixtures for FastApp tests."""

import pytest


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "company": "ACME",
    }


@pytest.fixture
def mock_database():
    """Mock database fixture placeholder."""
    pass


# Configure pytest-asyncio
pytest_plugins = ['pytest_asyncio']
