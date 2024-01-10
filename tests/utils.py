import os
import shutil
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Callable, NoReturn

from alembic import command as alem_command
from alembic.config import Config
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Engine, text

REPO_ROOT = Path(os.path.abspath(os.path.dirname(__file__))).parent.resolve()

ALEMBIC_COMMAND_MAP: dict[str, Callable[..., NoReturn]] = {
    "upgrade": alem_command.upgrade,
    "downgrade": alem_command.downgrade,
    "revision": alem_command.revision,
}


@contextmanager
def run_audit_logger_migrations(db: SQLAlchemy, alembic_config: Path):
    clear_alembic_migrations(db, alembic_config)
    run_alembic_command(
        engine=db.engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "1", "message": "create"},
        alembic_config=alembic_config,
    )

    run_alembic_command(
        engine=db.engine,
        command="upgrade",
        command_kwargs={"revision": "head"},
        alembic_config=alembic_config,
    )

    yield

    run_alembic_command(
        engine=db.engine,
        command="downgrade",
        command_kwargs={"revision": "base"},
        alembic_config=alembic_config,
    )
    clear_alembic_migrations(db, alembic_config)


def run_alembic_command(
    engine: Engine, command: str, command_kwargs: dict[str, Any], alembic_config: Path
) -> str:
    command_func = ALEMBIC_COMMAND_MAP[command]

    stdout = StringIO()

    alembic_cfg = Config(alembic_config / "alembic.ini")

    # Make double sure alembic references the test database
    alembic_cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    alembic_cfg.set_main_option("script_location", str(alembic_config))

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        with redirect_stdout(stdout):
            command_func(alembic_cfg, **command_kwargs)
    return stdout.getvalue()


def clear_alembic_migrations(db, alembic_config):
    with db.engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        connection.execute(
            text("DROP SCHEMA IF EXISTS audit_logs CASCADE; CREATE SCHEMA audit_logs;")
        )

    versions_root = alembic_config / "versions"

    # Remove any migrations that were left behind
    versions_root.mkdir(exist_ok=True, parents=True)
    shutil.rmtree(versions_root)
    versions_root.mkdir(exist_ok=True, parents=True)
