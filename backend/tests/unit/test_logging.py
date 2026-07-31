import json
import logging
from pathlib import Path

from loguru import logger

from app.core.config import PROJECT_ROOT, Settings, settings
from app.core.logging import complete_logging, configure_logging
from app.db import config as db_config


def test_logging_settings_normalize_values_and_use_data_path() -> None:
    app_settings = Settings(
        _env_file=None,
        log_level="debug",
        log_format="JSON",
    )

    assert app_settings.log_level == "DEBUG"
    assert app_settings.log_format == "json"
    assert Path(app_settings.log_file_path) == (
        PROJECT_ROOT / "data" / "logs" / "tadaask.log"
    )


async def test_logging_configuration_is_idempotent_and_intercepts_standard_logs(
    tmp_path: Path,
    capsys,
) -> None:
    log_file_path = tmp_path / "logs" / "test.log"
    app_settings = Settings(
        _env_file=None,
        log_level="INFO",
        log_format="json",
        log_file_enabled=True,
        log_file_path=str(log_file_path),
    )

    try:
        configure_logging(app_settings)
        configure_logging(app_settings)
        capsys.readouterr()

        logger.bind(job_uid="rag_test").info("application marker")
        logging.getLogger("uvicorn.error").warning("standard marker")
        await complete_logging()

        captured_records = [
            json.loads(line)["record"]
            for line in capsys.readouterr().err.splitlines()
            if line
        ]
        file_records = [
            json.loads(line)["record"]
            for line in log_file_path.read_text(encoding="utf8").splitlines()
            if line
        ]

        assert [record["message"] for record in captured_records] == [
            "application marker",
            "standard marker",
        ]
        assert [record["message"] for record in file_records] == [
            "application marker",
            "standard marker",
        ]
        assert captured_records[0]["extra"]["job_uid"] == "rag_test"
        assert captured_records[1]["extra"]["logging_name"] == "uvicorn.error"
        assert captured_records[1]["function"] == (
            "test_logging_configuration_is_idempotent_and_intercepts_standard_logs"
        )
        assert (
            logging.getLogger("sqlalchemy.orm").getEffectiveLevel() == logging.WARNING
        )
        assert logging.getLogger("uvicorn.access").disabled is True
        assert all(
            record["time"]["repr"].endswith("+00:00") for record in captured_records
        )
    finally:
        configure_logging(settings)
        await complete_logging()


def test_in_app_migration_keeps_application_logging(monkeypatch) -> None:
    class FakeAlembicConfig:
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}

    alembic_config = FakeAlembicConfig()
    upgrade_call: tuple[FakeAlembicConfig, str] | None = None

    def fake_upgrade(config: FakeAlembicConfig, revision: str) -> None:
        nonlocal upgrade_call
        upgrade_call = (config, revision)

    monkeypatch.setattr(db_config, "Config", lambda _: alembic_config)
    monkeypatch.setattr(db_config.command, "upgrade", fake_upgrade)

    db_config._run_alembic_upgrade()

    assert alembic_config.attributes["configure_logger"] is False
    assert upgrade_call == (alembic_config, "head")
