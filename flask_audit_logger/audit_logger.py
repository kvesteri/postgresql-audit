import os
import string
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property

from flask import request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    DDL,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    event,
    func,
    inspect,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, ExcludeConstraint, insert
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import ColumnProperty, relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.elements import TextClause

from flask_audit_logger import alembic

HERE = os.path.dirname(os.path.abspath(__file__))


class ImproperlyConfigured(Exception):
    pass


@dataclass
class PGExtension:
    schema: str
    signature: str

    @property
    def create_sql(self):
        return text(f"CREATE EXTENSION IF NOT EXISTS {self.signature} WITH SCHEMA {self.schema}")

    @property
    def drop_sql(self):
        return text(f"DROP EXTENSION IF EXISTS {self.signature}")


@dataclass
class PGFunction:
    schema: str
    signature: str
    create_sql: TextClause

    @property
    def drop_sql(self):
        return text(f'DROP FUNCTION IF EXISTS "{self.schema}"."{self.signature}" CASCADE')


@dataclass
class PGTrigger:
    schema: str
    signature: str
    table_name: str
    create_sql: TextClause

    @property
    def drop_sql(self):
        return text(f'DROP TRIGGER IF EXISTS "{self.signature}" ON "{self.table_name}"')


class AuditLogger(object):
    _actor_cls = None
    writer = None

    def __init__(
        self,
        db,
        get_actor_id=None,
        get_client_addr=None,
        actor_cls=None,
        schema=None,
    ):
        self._actor_cls = actor_cls or "User"
        self.get_actor_id = get_actor_id or _default_actor_id
        self.get_client_addr = get_client_addr or _default_client_addr
        self.schema = schema or "public"
        self.audit_logger_disabled = False
        self.db = db
        self.transaction_cls = _transaction_model_factory(db.Model, schema, self.actor_cls)
        self.activity_cls = _activity_model_factory(db.Model, schema, self.transaction_cls)
        self.versioned_tables = _detect_versioned_tables(db)
        self.attach_listeners()
        self.initialize_alembic_operations()

    def attach_listeners(self):
        """Listeners save transaction records with actor_ids when versioned tables are affected.
        Flush events occur when a mapped object is created or modified. ORM Execute events occur
        when an insert()/update()/delete() is passed to session.execute()."""
        event.listen(Session, "before_flush", self.receive_before_flush)
        event.listen(Session, "do_orm_execute", self.receive_do_orm_execute)

    def initialize_alembic_operations(self):
        alembic.setup_schema(self)
        alembic.setup_functions_and_triggers(self)
        self.writer = alembic.init_migration_ops(self.schema)

    def process_revision_directives(self, context, revision, directives):
        if self.writer:
            self.writer.process_revision_directives(context, revision, directives)

    @property
    def prefix(self):
        return f"{self.schema}." if self.schema != "public" else ""

    @cached_property
    def pg_entities(self):
        return [
            self.pg_btree_gist_extension,
            *self.pg_functions,
            *self.pg_triggers,
        ]

    @cached_property
    def pg_functions(self):
        return [
            self.pg_get_setting,
            self.pg_jsonb_subtract,
            self.pg_jsonb_change_key_name,
            self.pg_create_activity,
        ]

    @property
    def pg_triggers(self):
        return [t for triggers in self.pg_triggers_per_table.values() for t in triggers]

    @cached_property
    def pg_triggers_per_table(self):
        triggers_per_table = {}
        for table in self.versioned_tables:
            target_schema = table.schema or "public"
            versioned = table.info.get("versioned", {})
            excluded_columns = ""
            if "exclude" in versioned:
                joined_excludes = ",".join(versioned["exclude"])
                excluded_columns = "'{" + joined_excludes + "}'"

            triggers_per_table[table.name] = [
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_insert",
                    create_sql=self.render_sql_template(
                        "audit_trigger_insert.sql",
                        table_name=table.name,
                        excluded_columns=excluded_columns,
                    ),
                ),
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_update",
                    create_sql=self.render_sql_template(
                        "audit_trigger_update.sql",
                        table_name=table.name,
                        excluded_columns=excluded_columns,
                    ),
                ),
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_delete",
                    create_sql=self.render_sql_template(
                        "audit_trigger_delete.sql",
                        table_name=table.name,
                        excluded_columns=excluded_columns,
                    ),
                ),
            ]

        return triggers_per_table

    @property
    def functions_by_signature(self) -> dict[str, PGFunction]:
        return {pg_func.signature: pg_func for pg_func in self.pg_functions}

    @cached_property
    def pg_btree_gist_extension(self) -> PGExtension:
        return PGExtension(schema="public", signature="btree_gist")

    @property
    def pg_get_setting(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="get_setting(setting text, fallback text)",
            create_sql=self.render_sql_template("get_setting.sql"),
        )

    @property
    def pg_jsonb_subtract(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="jsonb_subtract(arg1 jsonb, arg2 jsonb)",
            create_sql=self.render_sql_template("jsonb_subtract.sql"),
        )

    @property
    def pg_jsonb_change_key_name(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="jsonb_change_key_name(data jsonb, old_key text, new_key text)",
            create_sql=self.render_sql_template("jsonb_change_key_name.sql"),
        )

    @property
    def pg_create_activity(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="create_activity()",
            create_sql=self.render_sql_template("create_activity.sql"),
        )

    @contextmanager
    def disable(self, session):
        session.execute(text("SET LOCAL flask_audit_logger.enable_versioning = 'false'"))
        self.audit_logger_disabled = True
        try:
            yield
        finally:
            self.audit_logger_disabled = False
            session.execute(text("SET LOCAL flask_audit_logger.enable_versioning = 'true'"))

    def render_sql_template(
        self, tmpl_name: str, as_text: bool = True, **kwargs
    ) -> TextClause | DDL:
        file_contents = _read_file(f"templates/{tmpl_name}").replace("$$", "$$$$")
        tmpl = string.Template(file_contents)
        context = dict(schema=self.schema)

        context["schema_prefix"] = "{}.".format(self.schema)
        context["revoke_cmd"] = ("REVOKE ALL ON {schema_prefix}activity FROM public;").format(
            **context
        )

        sql = tmpl.substitute(**context, **kwargs)

        if not as_text:
            return DDL(sql)

        return text(sql)

    def receive_do_orm_execute(self, orm_execute_state):
        is_write = (
            orm_execute_state.is_insert
            or orm_execute_state.is_update
            or orm_execute_state.is_delete
        )
        affects_versioned_table = any(
            m.local_table in self.versioned_tables for m in orm_execute_state.all_mappers
        )
        if is_write and affects_versioned_table:
            self.save_transaction(orm_execute_state.session)

    def receive_before_flush(self, session, flush_context, instances):
        if _is_session_modified(session, self.versioned_tables):
            self.save_transaction(session)

    def save_transaction(self, session):
        if self.audit_logger_disabled:
            return

        values = {
            "native_transaction_id": func.txid_current(),
            "issued_at": text("now() AT TIME ZONE 'UTC'"),
            "client_addr": self.get_client_addr(),
            "actor_id": self.get_actor_id(),
        }

        stmt = (
            insert(self.transaction_cls)
            .values(**values)
            .on_conflict_do_nothing(constraint="transaction_unique_native_tx_id")
        )
        session.execute(stmt)

    @property
    def actor_cls(self):
        if isinstance(self._actor_cls, str):
            if not self.db.Model:
                raise ImproperlyConfigured("No SQLAlchemy db object")
            registry = self.db.Model.registry._class_registry
            try:
                return registry[self._actor_cls]
            except KeyError:
                raise ImproperlyConfigured(
                    f"""Could not build relationship between AuditLogActivity
                    and {self._actor_cls}. {self._actor_cls} was not found in
                    declarative class registry. Either configure AuditLogger to
                    use different actor class or disable this relationship by
                    setting it to None."""
                )
        return self._actor_cls


def _transaction_model_factory(base, schema, actor_cls):
    if actor_cls:
        actor_pk = inspect(actor_cls).primary_key[0]
        actor_fk = ForeignKey(f"{actor_cls.__table__.name}.{actor_pk.name}")

    class AuditLogTransaction(base):
        __tablename__ = "transaction"

        id = Column(BigInteger, primary_key=True)
        native_transaction_id = Column(BigInteger)
        issued_at = Column(DateTime)
        client_addr = Column(INET)
        if actor_cls:
            actor_id = Column(actor_pk.type, actor_fk)
            actor = relationship(actor_cls)
        else:
            actor_id = Column(Text)

        __table_args__ = (
            ExcludeConstraint(
                (literal_column("native_transaction_id"), "="),
                (
                    literal_column("tsrange(issued_at - INTERVAL '1 HOUR', issued_at)"),
                    "&&",
                ),
                name="transaction_unique_native_tx_id",
            ),
            {"schema": schema},
        )

        def __repr__(self):
            return "<{cls} id={id!r} issued_at={issued_at!r}>".format(
                cls=self.__class__.__name__, id=self.id, issued_at=self.issued_at
            )

    return AuditLogTransaction


def _activity_model_factory(base, schema_name, transaction_cls):
    class AuditLogActivity(base):
        __tablename__ = "activity"
        __table_args__ = {"schema": schema_name}

        id = Column(BigInteger, primary_key=True)
        schema = Column(Text)
        table_name = Column(Text)
        relid = Column(Integer)
        issued_at = Column(DateTime)
        native_transaction_id = Column(BigInteger, index=True)
        verb = Column(Text)
        old_data = Column(JSONB, default={}, server_default="{}")
        changed_data = Column(JSONB, default={}, server_default="{}")
        transaction_id = Column(BigInteger, ForeignKey(transaction_cls.id))

        transaction = relationship(transaction_cls, backref="activities")

        @hybrid_property
        def data(self):
            data = self.old_data.copy() if self.old_data else {}
            if self.changed_data:
                data.update(self.changed_data)
            return data

        @data.expression
        def data(cls):
            return cls.old_data + cls.changed_data

        def __repr__(self):
            return ("<{cls} table_name={table_name!r} " "id={id!r}>").format(
                cls=self.__class__.__name__, table_name=self.table_name, id=self.id
            )

    return AuditLogActivity


def _read_file(file):
    with open(os.path.join(HERE, file)) as f:
        s = f.read()
    return s


def _default_actor_id():
    try:
        from flask_login import current_user
    except ImportError:
        return None

    try:
        return current_user.id
    except AttributeError:
        return None


def _default_client_addr():
    # Return None if we are outside of request context.
    return (request and request.remote_addr) or None


def _detect_versioned_tables(db: SQLAlchemy) -> set[Table]:
    versioned_tables = set()

    for table in db.metadata.tables.values():
        if table.info.get("versioned") is not None:
            versioned_tables.add(table)

    return versioned_tables


def _is_session_modified(session: Session, versioned_tables: set[Table]) -> bool:
    return any(
        _is_entity_modified(entity) or entity in session.deleted
        for entity in session
        if entity.__table__ in versioned_tables
    )


def _is_entity_modified(entity) -> bool:
    versioned = entity.__table__.info.get("versioned")
    excluded_cols = set(versioned.get("exclude", []))
    modified_cols = {column.name for column in _modified_columns(entity)}

    return bool(modified_cols - excluded_cols)


def _modified_columns(obj):
    columns = set()
    mapper = inspect(obj.__class__)
    for key, attr in inspect(obj).attrs.items():
        if key in mapper.synonyms.keys():
            continue
        prop = getattr(obj.__class__, key).property
        if attr.history.has_changes():
            columns |= set(
                prop.columns
                if isinstance(prop, ColumnProperty)
                else [local for local, remote in prop.local_remote_pairs]
            )

    return columns
