"""docs/spec/openapi-v0.json is the schema the code serves (api-contract-v0 section 5: changes show as a diff)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from par_app.api.app import openapi_document

pytestmark = pytest.mark.unit
STORED = Path(__file__).resolve().parents[2] / "docs" / "spec" / "openapi-v0.json"


def test_stored_schema_equals_the_code() -> None:
    stored = STORED.read_text(encoding="utf-8")
    assert stored == json.dumps(openapi_document(), ensure_ascii=False, indent=2) + "\n", (
        "docs/spec/openapi-v0.json is stale: run python tools/export_openapi.py"
    )


def test_served_schema_equals_the_stored_one(client: TestClient) -> None:
    assert client.get("/api/v0/openapi.json").json() == json.loads(STORED.read_text(encoding="utf-8"))


def test_schema_documents_400_not_422() -> None:
    document = openapi_document()
    responses = [code for path in document["paths"].values() for op in path.values() for code in op["responses"]]
    assert "422" not in responses
    assert "400" in responses and "503" in responses
