"""Unit tests for Document upload API (§3C1)."""

from __future__ import annotations

import io
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.documents import router


@pytest.mark.unit
class TestDocumentsAPI:
    @pytest.fixture
    def app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_upload_pdf(self, client: TestClient, tmp_path) -> None:
        with patch("src.api.routers.documents.Path") as mock_path:
            mock_path.return_value.suffix = ".pdf"
            mock_path.return_value.mkdir = lambda **kw: None
            content = b"%PDF-1.4 dummy content"
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
                data={"manufacturer": "ST"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert "task_id" in data

    def test_upload_invalid_extension(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_list_documents(self, client: TestClient) -> None:
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert "documents" in resp.json()

    def test_get_document(self, client: TestClient) -> None:
        resp = client.get("/api/v1/documents/1")
        assert resp.status_code == 200
