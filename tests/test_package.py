"""
Basic package tests to ensure FastApp can be imported and basic functionality works.
"""

import asyncio

import pytest

import fast_app


def test_package_version():
    """Test that package version is accessible."""
    assert hasattr(fast_app, '__version__')
    assert fast_app.__version__ == "0.3.2"


def test_package_author():
    """Test that package author is accessible."""
    assert hasattr(fast_app, '__author__')
    assert fast_app.__author__ == "Patrik Mojzis"


def test_package_metadata():
    """Test that all expected metadata is present."""
    assert hasattr(fast_app, '__email__')
    assert hasattr(fast_app, '__license__')
    assert hasattr(fast_app, '__url__')
    
    assert fast_app.__email__ == "patrikm53@gmail.com"
    assert fast_app.__license__ == "MIT"
    assert fast_app.__url__ == "https://github.com/patrikmojzis/fast-app"


@pytest.mark.asyncio
async def test_async_functionality():
    """Test that async functionality is available."""
    # Placeholder async test ensuring event loop works
    await asyncio.sleep(0)
    assert True
