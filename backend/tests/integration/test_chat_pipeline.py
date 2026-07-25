from datetime import datetime, timezone

import pytest
from app.api.admin.endpoints.chat_stream import (
    get_admin_rag_completer,
    get_admin_rag_provider_with_model,
)
from app.api.visitor.endpoints.chat import (
    get_rag_plugin,
    get_visitor_completer,
    get_visitor_model_settings,
    get_visitor_provider_with_model,
    valid_visitor_stream_project,
)
from app.core.security import get_password_hash
from app.db.models import Admin, Project, ProjectSettings, ProjectWidget
from app.db.schemas import ModelProfileRead, ProviderWithModelInternalRead
from app.providers import ModelSettings
from tests.helpers import FakeCompleter


pytestmark = pytest.mark.integration


def provider_with_model() -> ProviderWithModelInternalRead:
    now = datetime.now(timezone.utc)
    return ProviderWithModelInternalRead(
        uid="provider",
        name="fake",
        created_at=now,
        updated_at=now,
        model_profile=ModelProfileRead(
            uid="model",
            model="fake-model",
            context_window_tokens=10_000,
            max_output_tokens=100,
            created_at=now,
            updated_at=now,
        ),
    )


@pytest.mark.asyncio
async def test_admin_chat_sse_uses_fake_provider_and_persists_messages(
    app, client, db_session, session_factory
) -> None:
    db_session.add(Admin(username="admin", password_hash=get_password_hash("secret")))
    await db_session.commit()
    fake = FakeCompleter(chunks=["hello", " world"])

    async def fake_provider():
        return provider_with_model()

    async def fake_completer():
        return fake

    app.dependency_overrides[get_admin_rag_provider_with_model] = fake_provider
    app.dependency_overrides[get_admin_rag_completer] = fake_completer
    login = await client.post(
        "/admin/auth/login", data={"username": "admin", "password": "secret"}
    )
    response = await client.post(
        "/admin/chat/stream",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"message": "hello", "providerUid": "provider", "modelUid": "model"},
    )

    assert response.status_code == 200
    assert "event: session_ready" in response.text
    assert "event: delta" in response.text
    assert "event: message_done" in response.text
    assert fake.stream_calls
    stream_messages, stream_settings = fake.stream_calls[0]
    assert stream_messages[-1].content == "hello"
    assert stream_settings.max_tokens == 100
    assert fake.last_stream and fake.last_stream.closed

    from app.crud import ChatMessageCRUD, ChatSessionCRUD

    async with session_factory() as session:
        sessions = await ChatSessionCRUD(session).list_admin_global_sessions()
        messages = await ChatMessageCRUD(session).list_messages_for_context(
            chat_session_id=sessions[0].id
        )
    assert [(message.role.value, message.message) for message in messages] == [
        ("user", "hello"),
        ("assistant", "hello world"),
    ]


@pytest.mark.asyncio
async def test_visitor_widget_chat_allows_matching_origin_and_rejects_disabled_widget(
    app,
    client,
    db_session,
) -> None:
    project = Project(name="Widget project")
    project.project_settings = ProjectSettings(visitor_rag_enabled=False)
    db_session.add(project)
    await db_session.flush()
    widget = ProjectWidget(
        project_id=project.id,
        name="Widget",
        site_origin="https://example.test",
    )
    db_session.add(widget)
    await db_session.commit()

    async def loaded_project():
        return project

    async def fake_provider():
        return provider_with_model()

    async def fake_completer():
        return FakeCompleter(chunks=["visitor answer"])

    async def fake_settings():
        return ModelSettings.for_compaction()

    async def no_rag():
        return None

    app.dependency_overrides[valid_visitor_stream_project] = loaded_project
    app.dependency_overrides[get_visitor_provider_with_model] = fake_provider
    app.dependency_overrides[get_visitor_completer] = fake_completer
    app.dependency_overrides[get_visitor_model_settings] = fake_settings
    app.dependency_overrides[get_rag_plugin] = no_rag
    url = f"/visitor/project/{project.uid}/widget/{widget.uid}/chat/stream"
    allowed = await client.post(
        url, headers={"Origin": "https://example.test"}, json={"message": "hello"}
    )

    widget.is_enabled = False
    await db_session.commit()
    rejected = await client.post(
        url, headers={"Origin": "https://example.test"}, json={"message": "hello"}
    )

    assert allowed.status_code == 200
    assert "event: message_done" in allowed.text
    assert rejected.status_code == 403
