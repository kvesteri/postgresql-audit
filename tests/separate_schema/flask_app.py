import os
from datetime import datetime
from typing import Optional

from flask import Flask
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from flask_audit_logger import AuditLogger

db_user = os.environ.get("FLASK_AUDIT_LOGGER_TEST_USER", "postgres")
db_password = os.environ.get("FLASK_AUDIT_LOGGER_TEST_PASSWORD", "")
db_name = os.environ.get("FLASK_AUDIT_LOGGER_TEST_DB", "flask_audit_logger_test")
db_conn_str = f"postgresql://{db_user}:{db_password}@localhost/{db_name}"


class Base(MappedAsDataclass, DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()


class User(db.Model, UserMixin):
    __tablename__ = "user"
    __table_args__ = ({"info": {"versioned": {"exclude": ["age", "height"]}}},)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[Optional[int]] = mapped_column(default=None)
    height: Mapped[Optional[int]] = mapped_column(default=None)


class Article(db.Model):
    __tablename__ = "article"
    __table_args__ = ({"info": {"versioned": {"exclude": ["created"]}}},)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created: Mapped[datetime] = mapped_column(insert_default=datetime.now)


@login_manager.user_loader
def load_user(id):
    return db.session.get(User, id)


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = db_conn_str
app.secret_key = "secret"
app.debug = True

db.init_app(app)
login_manager.init_app(app)

audit_logger = AuditLogger(db, schema="audit_logs")
AuditLogActivity = audit_logger.activity_cls
