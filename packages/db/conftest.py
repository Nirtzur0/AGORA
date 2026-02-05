"""
Pytest configuration for database tests.
"""
import pytest
import os
import sys

# Add the current directory to sys.path so that 'db' module can be imported
sys.path.append(os.path.dirname(__file__))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real DB)"
    )
