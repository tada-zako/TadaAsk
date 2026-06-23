from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.admin.router import get_current_admin
from app.api.deps import (
    get_admin_crud,
    get_project_crud,
    get_visitor_rate_limiter,
    valid_project_with_settings,
)
from app.core.security import get_password_hash
from app.main import app


class FakeAdminCRUD:
    def __init__(self) -> None:
        self.admin = SimpleNamespace(
            username="admin",
            password_hash=get_password_hash("admin123"),
            token_version=0,
        )

    async def get_admin_by_username(self, username: str):
        if username == self.admin.username:
            return self.admin
        return None


class FakeProjectCRUD:
    def __init__(self) -> None:
        self.project = None

    async def list_projects(self, *, limit: int, offset: int):
        return [] if self.project is None else [self.project]

    async def create_project(self, *, project_data):
        self.project = SimpleNamespace(
            id=1,
            uid="project-uid",
            name=project_data.name,
            description=project_data.description,
            site_url=project_data.site_url,
            created_at=datetime.now(timezone.utc),
            visitor_default_model_profile=None,
        )
        return self.project

    async def get_project_by_uid(self, *, project_uid: str):
        if self.project and project_uid == self.project.uid:
            return self.project
        return None

    async def get_project_settings_by_project_id(self, *, project_id: int):
        return SimpleNamespace(
            visitor_rag_enabled=True,
            visitor_system_prompt=None,
            visitor_max_output_tokens=1536,
            visitor_temperature=0.3,
            visitor_top_p=0.9,
            visitor_timeout=45.0,
            visitor_thinking=False,
            rag_mode="fast",
            rag_top_k=8,
            rag_rerank_enabled=True,
            rag_fts_k=30,
            rag_vector_k=20,
            rag_rerank_k=12,
            rag_max_alternative_queries=2,
            rag_max_keywords=5,
            rag_standalone_enabled=False,
            visitor_default_provider=None,
            visitor_default_model_profile=None,
        )


class FakeVisitorRateLimiter:
    async def check_request(self, *, ip: str, project_uid: str) -> None:
        return None

    async def acquire_stream(self, *, ip: str, project_uid: str):
        return SimpleNamespace(ip=ip, project_uid=project_uid)

    async def release_stream(self, lease) -> None:
        return None


@pytest.fixture()
def client():
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_admin_login_success_and_failure(client: TestClient) -> None:
    app.dependency_overrides[get_admin_crud] = lambda: FakeAdminCRUD()

    failed = client.post(
        "/admin/auth/login",
        data={"username": "admin", "password": "wrong"},
    )
    ok = client.post(
        "/admin/auth/login",
        data={"username": "admin", "password": "admin123"},
    )

    assert failed.status_code == 401
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    assert ok.json()["access_token"]


def test_admin_project_list_requires_auth(client: TestClient) -> None:
    response = client.get("/admin/project/list")

    assert response.status_code == 401


def test_admin_project_basic_flow_with_auth_override(client: TestClient) -> None:
    project_crud = FakeProjectCRUD()
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(username="admin")
    app.dependency_overrides[get_project_crud] = lambda: project_crud

    created = client.post(
        "/admin/project/new",
        json={
            "name": "Smoke Project",
            "siteUrl": "https://smoke.example.com",
            "description": "smoke",
        },
    )
    listed = client.get("/admin/project/list")
    detail = client.get("/admin/project/project-uid")
    settings = client.get("/admin/project/project-uid/settings")

    assert created.status_code == 200
    assert created.json()["uid"] == "project-uid"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert detail.status_code == 200
    assert settings.status_code == 200
    assert settings.json()["visitorDefaultProvider"] is None


def test_visitor_chat_reports_missing_model_configuration(client: TestClient) -> None:
    async def reject_project():
        raise HTTPException(
            status_code=400,
            detail="Visitor default provider or model not configured for the project, please check if the project settings are properly initialized.",
        )

    app.dependency_overrides[valid_project_with_settings] = reject_project
    app.dependency_overrides[get_visitor_rate_limiter] = lambda: FakeVisitorRateLimiter()

    response = client.post(
        "/visitor/project/project-uid/chat/stream",
        json={"message": "hello"},
    )

    assert response.status_code == 400
    assert "Visitor default provider or model not configured" in response.text
