"""The UI's TypeScript types are generated from ui/openapi.json, which must match the live API schema."""

from __future__ import annotations

import json

from photoedit.api import create_app
from photoedit.config import DEFAULT_PROJECT_ROOT, Settings

SCHEMA_FILE = DEFAULT_PROJECT_ROOT / "ui" / "openapi.json"


def test_committed_openapi_schema_is_current(settings: Settings) -> None:
    committed = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    live = create_app(settings).openapi()
    assert committed == live, "ui/openapi.json is out of date: run `npm --prefix ui run gen:api`"
