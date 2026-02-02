"""
Pytest configuration for database tests.
"""
import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real DB)"
    )
