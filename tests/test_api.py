from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from photoedit import __version__
from photoedit.api import create_app
from photoedit.config import Settings


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def built_ui(settings: Settings) -> Path:
    dist = settings.ui_dist_dir
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    return dist


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__}


def test_unknown_api_route_is_json_404(client: TestClient) -> None:
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_ui_not_built_page(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "not built" in r.text


def test_serves_built_index(client: TestClient, built_ui: Path) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "INDEX" in r.text


def test_serves_static_asset(client: TestClient, built_ui: Path) -> None:
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_spa_route_falls_back_to_index(client: TestClient, built_ui: Path) -> None:
    r = client.get("/library/some/photo")
    assert r.status_code == 200
    assert "INDEX" in r.text


def test_path_traversal_does_not_escape_ui_dist(
    client: TestClient, built_ui: Path, settings: Settings
) -> None:
    secret = settings.project_root / "secret.txt"
    secret.write_text("SECRET", encoding="utf-8")
    for url in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2f..%2fsecret.txt"):
        r = client.get(url)
        assert "SECRET" not in r.text, url


def test_head_request_on_ui_is_allowed(client: TestClient, built_ui: Path) -> None:
    assert client.head("/").status_code == 200


def test_openapi_lists_health(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/health" in schema["paths"]
