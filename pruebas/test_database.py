import os

import pytest
from sqlalchemy import text
from sqlmodel import create_engine

from api.database import database_url


pytestmark = pytest.mark.skipif(
    os.getenv("PATHFINDER_TEST_DB") != "1",
    reason="Requires isolated PostgreSQL test server",
)


@pytest.fixture
def db_url(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5434")
    monkeypatch.setenv("POSTGRES_DB", "pathfinder_test")
    monkeypatch.setenv("POSTGRES_USER", "pathfinder")
    return database_url()


def test_database_connection(db_url):
    engine = create_engine(db_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar() == 1
    finally:
        engine.dispose()


@pytest.fixture
def empty_db_url(db_url, monkeypatch):
    from uuid import uuid4

    name = f"test_{uuid4().hex}"
    admin = create_engine(db_url, isolation_level="AUTOCOMMIT")

    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))

        try:
            monkeypatch.setenv("POSTGRES_DB", name)
            yield db_url.set(database=name)
        finally:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}"'))
    finally:
        admin.dispose()


def test_migrations_from_empty(empty_db_url):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    engine = create_engine(empty_db_url)

    try:
        assert inspect(engine).get_table_names() == []

        command.upgrade(Config("alembic.ini"), "head")

        tables = inspect(engine).get_table_names()
        assert "users" in tables
        assert "alembic_version" in tables
    finally:
        engine.dispose()


def test_schema_consistency(empty_db_url):
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.check(config)


def test_user_persistence(empty_db_url):
    from alembic import command
    from alembic.config import Config
    from sqlmodel import Session, select
    from api.models import User

    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(empty_db_url)

    try:
        with Session(engine) as session:
            user = User(
                email="demo@example.com",
                password_hash="synthetic-test-hash",
            )
            session.add(user)
            session.commit()

        with Session(engine) as session:
            saved = session.exec(
                select(User).where(User.email == "demo@example.com")
            ).one()

            assert saved.email == "demo@example.com"
            assert saved.password_hash == "synthetic-test-hash"
            assert saved.id is not None
    finally:
        engine.dispose()


@pytest.fixture
def migrated_engine(empty_db_url):
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(empty_db_url)

    try:
        yield engine
    finally:
        engine.dispose()


def test_unique_email(migrated_engine):
    from sqlalchemy.exc import IntegrityError
    from sqlmodel import Session
    from api.models import User

    with Session(migrated_engine) as session:
        session.add(User(
            email="duplicate@example.com",
            password_hash="test-hash",
        ))
        session.commit()

        session.add(User(
            email="duplicate@example.com",
            password_hash="another-hash",
        ))

        with pytest.raises(IntegrityError) as error:
            session.commit()

        assert error.value.orig.sqlstate == "23505"
        session.rollback()


def test_required_fields(migrated_engine):
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError
    from api.models import User

    for field in ("id", "email", "password_hash"):
        values = {
            "id": uuid4(),
            "email": "required@example.com",
            "password_hash": "test-hash",
        }
        values[field] = None

        with pytest.raises(IntegrityError) as error:
            with migrated_engine.begin() as connection:
                connection.execute(
                    User.__table__.insert().values(**values)
                )

        assert error.value.orig.sqlstate == "23502"
        assert error.value.orig.diag.column_name == field


def test_transaction_rollback(migrated_engine):
    from sqlalchemy.exc import IntegrityError
    from sqlmodel import Session, select
    from api.models import User

    with Session(migrated_engine) as session:
        session.add(User(
            email="rollback@example.com",
            password_hash="test-hash",
        ))
        session.flush()

        session.add(User(
            email="rollback@example.com",
            password_hash="duplicate-hash",
        ))

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()

    with Session(migrated_engine) as session:
        assert session.exec(select(User)).all() == []
