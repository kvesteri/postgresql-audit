# Changelog
---------

Here you can see the full list of changes between each flask-audit-logger release.

# 1.0.0 (2023-12-29)

- Rename `VersioningManager` to `AuditLogger`
- Update to work with alembic
- Update README


# 0.17.1 (2023-11-06)

- Fix package name to be in lowercase in `pyproject.toml`.


# 0.17.0 (2023-11-04)

- Use the `pyproject.toml` standard to specify project metadata, dependencies and tool configuration. Use Hatch to build the project.
- Make the documentation buildable again.
- Fix some grammar and formatting issues in the documentation
- Refactor `VersioningManager.audit_table()` method and extract the query building logic into a new method `VersioningManager.build_audit_table_query()`.
- Fix a deprecation warning about `sqlalchemy.orm.mapper()` symbol usage on SQLAlchemy 2.0.

# 0.16.0 (2023-08-04)

- **BREAKING CHANGE**: Drop support for PostgreSQL 9.5, 9.6 and 10, which have reached end of their lives.
- Add support for SQLAlchemy 2.0
- Remove unused `VersioningManager.cached_ddls` attribute
- Removed redundant statement caching from `VersioningManager.audit_table`

# 0.15.0 (2023-05-15)

- **BREAKING CHANGE**: `flask.activity_values` doesn't require request context (#75, courtesy of tvuotila)
- **BREAKING CHANGE**: Drop support for Python 3.7
- Fix some SQLAlchemy 2.0 deprecation warnings (#76, courtesy of tchapi)
- Remove unnecessary checks for Flask request context
- Remove unnecessary `__future__` import

# 0.14.1 (2023-04-26)

- Fix compatibility with Flask-SQLAlchemy<3.0

# 0.14.0 (2023-04-26)

- **BREAKING CHANGE**: Drop support for Python 3.6, which reached the end of its life on December 23rd, 2021.
- **BREAKING CHANGE**: Drop support for SQLAlchemy 1.1, 1.2 and 1.3, which are no longer maintained.
- Fix `SAWarning` from SQLAlchemy 1.4 about missing `inherit_cache` attribute
- Fix deprecation warnings from Flask 2.2 about `_app_ctx_stack.top` and `_request_ctx_stack.top` usage.
- Add support for Flask-SQLAlchemy 3.0
- Add support for Python 3.10 and 3.11

# 0.13.0 (2021-05-16)

- Add SQLAlchemy 1.4 support
- Add Python 3.9 support
- **BREAKING CHANGE**: Drop Python 2.7 and 3.5 support. Python 2.7 reached the end of its life on January 1st, 2020 and Python 3.5 on September 13th, 2020.

# 0.12.4 (2020-02-18)

- Specify the column names when inserting new audit rows (#49, courtesy of quantus)


# 0.12.3 (2020-01-16)

- Added nesting of activity values (#48, courtesy of tvuotila)


# 0.12.2 (2019-11-12)

- Made disable context manager use a finally block (#42, courtesy of ElPicador)


# 0.12.1 (2019-10-18)

- Added commits missing from 0.12.0


# 0.12.0 (2019-10-15)

- Create only single transaction per database transaction (#37)


# 0.11.1 (2019-03-20)

- Fixed `flask_audit_logger.enable_versioning` parameter to work in situations where the transaction is rolled back and this parameter is set by the rollback operation as an empty string.


# 0.11.0 (2019-03-10)

- Changed the use of `session_replication_role` to `flask_audit_logger.enable_versioning` parameter. This change was made in order to allow temporarly disable versioning in environments such as Heroku where changing `session_replication_role` configuration setting even on transaction level is impossible. (#31)
- Drop and create `jsonb_substract` function instead of replacing it (#29, courtesy of AdamSelene)


# 0.10.0 (2018-07-20)

- Added support for PostgreSQL 10 statement level trigger transition tables. Huge performance boost for heavy inserts.


# 0.9.3 (2018-05-13)

- Force timestamps to use UTC as timezone (#30, courtesy of quantus)
- Dropped Python 3.3 support


# 0.9.2 (2017-12-13)

- Added PostgreSQL 10 support


# 0.9.1 (2017-10-10)

- Fixed `jsonb_subtract` (jsonb - jsonb) support for arrays as values


# 0.9.0 (2017-09-06)

- Added different PostgreSQL versions (9.4, 9.5 and 9.6) to test matrix
- Defined activity `old_data` and `changed_data` defaults as empty JSONBs
- Made `Activity.data` use new 9.6 JSONB `concat` operator. On PostgreSQL 9.5 and 9.4 this still uses fallback function.


# 0.8.4 (2016-03-27)

- Allowed passing `transaction_cls` parameter to `activity_base` function (#23, pull request courtesy jmagnusson)


# 0.8.3 (2016-08-20)

- Fixed Flask ExtDeprecationWarnings (#17, courtesy of jpvanhal)


# 0.8.2 (2016-08-20)

- Added a workaround for SQLAlchemy issue #3778


# 0.8.1 (2016-08-20)

- Fixed `modified_columns` method to work with synonym properties


# 0.8.0 (2016-08-03)

- Added `transaction` table
- Moved `actor_id` and `client_addr` columns to `transaction` table


# 0.7.0 (2016-03-06)

- Added support for PostgreSQL 9.5. Certain JSONB subtraction operators are only created if used PostgreSQL version is below 9.5.
- Added `rename_table` migration function


# 0.6.0 (2016-01-13)

- Added support for activity schema configuration (#4, courtesy of jmagnusson)


# 0.5.2 (2016-01-09)

- Avoid empty string INET value with Flask `VersioningManager` (#10, courtesy of asfaltboy)


# 0.5.1 (2015-04-14)

- Fixed migration helpers to work with alembic operations object


# 0.5.0 (2015-04-13)

- Added `alter_column` migration helper function
- Added `change_column_name` migration helper function
- Added flake8 checks
- Added isort checks
- Added `jsonb_change_key_name` function expression
- Added `jsonb` substraction operator to support text data type
- Added `remove_column` migration helper


# 0.4.2 (2015-03-13)

- Added `data` `hybrid_property` for `Activity` model. This property makes it easy to find all changes made in given record.


# 0.4.1 (2015-03-13)

- Made `client_addr` overridable
- Removed `client_port` column from `activity` table (doesn't make sense in web environment)


# 0.4.0 (2015-03-12)

- Added default value for `audit_table` exclude parameter
- Changed `row_data` and `changed_fields` types from HSTORE to JSONB
- Removed `object_id` column from `activity` table
- Renamed `row_data` to `old_data` and `changed_fields` to `changed_data`


# 0.3.0 (2015-02-24)

- Added Flask extension
- Rewrote activity values setting. Now values are set after the flush phase occurs.


# 0.2.3 (2015-02-21)

- Added explicit committing of `audit_table` ddl statements


# 0.2.2 (2015-02-21)

- Made `actor_id` and `actor` properties of `Activity` model configured during mapper configuration phase


# 0.2.1 (2015-02-20)

- Added `audit_table` function


# 0.2.0 (2015-02-19)

- Added `__versioned__` configuration parameter for models
- Added customizable column exclusion support for versioned models


# 0.1.7 (2015-02-18)

- Removed foreign key from `actor_id` in `Activity` model


# 0.1.6 (2015-02-18)

- Added support for callables as activity values
- Changed composite primary key separator from ',' to '|'


# 0.1.5 (2015-02-18)

- Fixed pypi setup


# 0.1.4 (2015-02-18)

- Made `actor` class and `actor_id` column customizable


# 0.1.3 (2015-02-17)

- Made all file reads use absolute paths


# 0.1.2 (2015-02-17)

- Removed all default indexes from activity table


# 0.1.1 (2015-02-17)

- Added `__repr__` for activity classes
- Removed session user name column from activity table
- Removed application name column from activity table


# 0.1 (2015-02-17)

- Initial public release
