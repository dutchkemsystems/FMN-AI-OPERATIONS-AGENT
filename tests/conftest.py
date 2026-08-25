"""Pytest configuration for FMN-AI test suite."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./fmn_test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_PASSWORD"] = "test123"
os.environ["ADMIN_USERNAME"] = "testadmin"
