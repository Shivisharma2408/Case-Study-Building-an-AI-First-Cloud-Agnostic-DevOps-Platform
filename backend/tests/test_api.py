from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", max_idea_length=50)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz(client: TestClient) -> None:
    assert client.get("/readyz").json() == {"status": "ready"}


def test_list_is_empty_initially(client: TestClient) -> None:
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_returns_created_idea(client: TestClient) -> None:
    resp = client.post("/api/ideas", json={"content": "  Ship it  "})
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "Ship it"  # whitespace stripped
    assert isinstance(body["id"], int)
    assert body["created_at"]


def test_list_returns_newest_first(client: TestClient) -> None:
    for text in ("first", "second", "third"):
        assert client.post("/api/ideas", json={"content": text}).status_code == 201
    contents = [idea["content"] for idea in client.get("/api/ideas").json()]
    assert contents == ["third", "second", "first"]


@pytest.mark.parametrize(
    "payload",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 51},  # over the configured max length
        {"content": "bad\x00byte"},
        {"content": 123},
        {},
        {"content": "ok", "extra": "field"},
    ],
)
def test_invalid_payloads_are_rejected(client: TestClient, payload: dict[str, object]) -> None:
    resp = client.post("/api/ideas", json=payload)
    assert resp.status_code == 422
    assert client.get("/api/ideas").json() == []


def test_settings_build_url_from_discrete_vars() -> None:
    settings = Settings(
        db_host="db.internal", db_user="app", db_password="p@ss:w/rd", db_name="ideas"
    )
    assert settings.sqlalchemy_url == (
        "postgresql+psycopg://app:p%40ss%3Aw%2Frd@db.internal:5432/ideas?sslmode=prefer"
    )


def test_database_url_takes_precedence() -> None:
    settings = Settings(database_url="sqlite://", db_host="ignored")
    assert settings.sqlalchemy_url == "sqlite://"
