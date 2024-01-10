# Flask Audit Logger

Auditing extension for [Flask](https://flask.palletsprojects.com/en/3.0.x/) using [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/3.1.x/), [Alembic](https://alembic.sqlalchemy.org/en/latest/index.html), and [PostgreSQL](https://www.postgresql.org/).
This package tracks changes to database records within specified tables.
The current user affecting the target table will also be recorded.

- Stores versioned records with old and changed data in an `activity` table
- Uses database triggers to record activity records, keeping INSERTs, UPDATEs and DELETEs as fast as possible
- Uses SQLAlchemy events to track actor IDs in a `transaction` table
- Tables and triggers can be easily configured using Alembic migrations

This project was forked from [PostgreSQL-Audit](https://github.com/kvesteri/postgresql-audit), but does not attempt to maintain backwards compatability.
It draws inspiration from other projects such as [SQLAlchemy-Continuum](https://github.com/kvesteri/SQLAlchemy-Continuum), [Papertrail](https://github.com/airblade/paper_trail), and [Audit Trigger](https://github.com/2ndQuadrant/audit-trigger).

## Installation
```
pip install flask-audit-logger
```

## Setup
Create a single `AuditLogger()` instance _after_ your models have been declared. E.g. in `app/models.py`:
```python
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy
from flask_audit_logger import AuditLogger

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    __table_args__ = ({"info": {"versioned": {}}},)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, auto_increment=True)
    name: Mapped[str]

# ... more model declarations ...

audit_logger = AuditLogger(db)
```
Identify the tables you want audited by adding `{"info": {"versioned": {}}}` to a model's `__table_args__`.
The `"versioned"` key determines which tables get database triggers.

Next, configure `migrations/env.py` so the AuditLogger can rewrite migration files.
This assumes you have already initialized your project to handle database migrations with Alembic.
```python
from alembic import context
from app.models import audit_logger

def run_migrations_online():
    # ...
    context.configure(
        # ...
        process_revision_directives=audit_logger.process_revision_directives,
    )
```
There's typically a lot going on in the `env.py` file.
You may need to call `audit_logger.process_revision_directives()` inside an existing function.

Finally, run the migration which will create audit tables, functions, and triggers.
Here I'm using [Flask-Migrate](https://flask-migrate.readthedocs.io/en/latest/), but you can use Alembic directly if you wish.
```
flask db migrate -m 'setup audit_logger'
flask db upgrade
```
If you need an audit trail for another table in the future, add `{"info": {"versioned": {}}` to the `__table_args__` tuple.
When you generate the next migration, the newly versioned table will be detected and the correct triggers will get created. 


## Features
### Determining actor_id
By default, `transaction.actor_id` will be set using [`flask_login.current_user`](https://flask-login.readthedocs.io/en/latest/#flask_login.current_user).
Use the `get_actor_id` constructor option if you want to change this behavior:
```python
from flask import g

def get_current_user_id():
    return g.my_current_user.id

audit_logger = AuditLogger(db, get_actor_id=get_current_user_id)
```

### Changing the AuditLogger schema
The `activity` and `transaction` tables are created in the `public` schema by default.
If you want these tables to live in a different schema, pass in the schema name when you instantiate the AuditLogger.
```python
audit_logger = AuditLogger(db, schema="audit_logs")
```

You will also need to make sure Alembic supports multiple schemas.
This can be done through an `env.py` configuration.
```python
def run_migrations_online():
    # ...
    context.configure(
        # ...
        include_schemas=True,  # required for alembic to manage more than the 'public' schema
        process_revision_directives=audit_logger.process_revision_directives,
    )
```

### Customizing actor_cls
The `AuditLogger.actor_cls` should align with your current_user type.
By default, this package assumes the `User` model is also the actor class.
This can be customized by passing in the model name as a string when the AuditLogger is created.
```python
audit_logger = AuditLogger(db, actor_cls="SuperUser")
```
This model will be used to populate the `AuditLogTransaction.actor` relationship.
For example, the following query loads the first activity and its responsible actor.
```python
AuditLogActivity = audit_logger.activity_cls
AuditLogTransaction = audit_logger.transaction_cls

activity = db.session.scalar(
    select(AuditLogActivity)
    .options(joinedload(AuditLogActivity.transaction).joinedload(AuditLogTransaction.actor))
    .limit(1)
)

print(activity.transaction.actor)
<SuperUser 123456>
```


### Excluding Columns
You may want to ignore version tracking on specific database columns.
This can be done by adding `"exclude"` with a list of column names to `__table_args__`.
```python
# app/models.py
class User(db.Model):
    __tablename__ = "users"
    __table_args__ = ({"info": {"versioned": {"exclude": ["hair_color"]}}},)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, auto_increment=True)
    name: Mapped[str]
    hair_color: Mapped[str]


# flask db migrate -m 'exclude hair_color'
#   migrations/versions/xxxx_exclude_hair_color.py
def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.init_audit_logger_triggers("users", excluded_columns=["hair_color"])
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.remove_audit_logger_triggers("users")
    # ### end Alembic commands ###
```


## Known Limitations
- This package does not play nicely with [Alembic Utils](https://github.com/olirice/alembic_utils)
- Changes to `excluded_columns` are not remembered. You will need to edit `downgrade_()` manually to properly revert changes
- The test suite must be run with multiple `pytest` commands. Because Alembic, Flask-SQLAlchemy, etc. only work with one `Flask()` instance, the different `AuditLogger` configurations require separate test apps.