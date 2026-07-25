import pytest
from app.api.schemas import RAGSyncEvent
from app.core.constants import IngestStage, RAGJobType, RAGSyncEventType
from app.core.security import get_password_hash
from app.db.models import Admin


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_admin_auth_project_source_upload_and_job_entrypoint(
    app,
    client,
    db_session,
) -> None:
    db_session.add(Admin(username="admin", password_hash=get_password_hash("secret")))
    await db_session.commit()

    login = await client.post(
        "/admin/auth/login",
        data={"username": "admin", "password": "secret"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/admin/auth/me", headers=headers)
    project = await client.post(
        "/admin/project/new", headers=headers, json={"name": "API project"}
    )
    source = await client.post(
        "/admin/source/new",
        headers=headers,
        json={"sourceName": "API source", "sourceType": "local_file"},
    )
    source_uid = source.json()["uid"]
    uploaded = await client.post(
        f"/admin/source/{source_uid}/items/upload",
        headers=headers,
        files={"files": ("guide.txt", b"API pipeline deployment guide", "text/plain")},
    )
    item_uid = uploaded.json()[0]["uid"]
    job = await client.post(
        f"/admin/source/{source_uid}/document/indexing",
        headers=headers,
        json={"itemUids": [item_uid]},
    )
    job_state = await client.get(
        f"/admin/source/jobs/{job.json()['jobUid']}", headers=headers
    )
    running_job = app.state.rag_job_manager.get_job(job.json()["jobUid"])
    assert running_job is not None
    await running_job.task
    completed_job_state = await client.get(
        f"/admin/source/jobs/{job.json()['jobUid']}", headers=headers
    )

    assert login.status_code == me.status_code == project.status_code == 200
    assert source.status_code == uploaded.status_code == 200
    assert job.status_code == 202
    assert job_state.status_code == 200
    assert job_state.json()["sourceUid"] == source_uid
    assert completed_job_state.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_rag_job_sse_replays_events_after_last_event_id(
    app, client, db_session
) -> None:
    db_session.add(Admin(username="admin", password_hash=get_password_hash("secret")))
    await db_session.commit()
    login = await client.post(
        "/admin/auth/login",
        data={"username": "admin", "password": "secret"},
    )
    manager = app.state.rag_job_manager

    async def runner(_):
        for message in ("first", "second"):
            yield RAGSyncEvent(
                event=RAGSyncEventType.SYNC_PROGRESS,
                source_uid="source",
                ingest_stage=IngestStage.LOADING,
                message=message,
            )

    job = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="source",
        runner=runner,
    )
    await job.task

    replay = await client.get(
        f"/admin/source/jobs/{job.job_uid}/events",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}",
            "Last-Event-ID": "1",
        },
    )

    assert replay.status_code == 200
    assert "id: 2" in replay.text
    assert "event: sync_progress" in replay.text
    assert '"message": "second"' in replay.text
