import pytest
from pydantic import ValidationError

from app.config import Settings


def test_wildcard_frontend_origin_rejected():
    with pytest.raises(ValidationError):
        Settings(frontend_origin="*")


def test_explicit_frontend_origin_accepted():
    s = Settings(frontend_origin="http://localhost:3000")
    assert s.frontend_origin == "http://localhost:3000"
