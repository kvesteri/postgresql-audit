Changelog
---------

Here you can see the full list of changes between each PostgreSQL-Audit release.


0.8.1 (2016-08-20)
^^^^^^^^^^^^^^^^^^

- Fixed modified_columns method to work with synonym properties


0.8.0 (2016-08-03)
^^^^^^^^^^^^^^^^^^

- Added transaction table
- Moved actor_id and client_addr columns to transaction table


0.7.0 (2016-03-06)
^^^^^^^^^^^^^^^^^^

- Added support for PostgreSQL 9.5. Certain JSONB subtraction operators are only created if used PostgreSQL version is below 9.5.
- Added rename_table migration function


0.6.0 (2016-01-13)
^^^^^^^^^^^^^^^^^^

- Added support for activity schema configuration (#4, courtesy of jmagnusson)


0.5.2 (2016-01-09)
^^^^^^^^^^^^^^^^^^

- Avoid empty string INET value with Flask VersioningManager (#10, courtesy of asfaltboy)


0.5.1 (2015-04-14)
^^^^^^^^^^^^^^^^^^

- Fixed migration helpers to work with alembic operations object


0.5.0 (2015-04-13)
^^^^^^^^^^^^^^^^^^

- Added alter_column migration helper function
- Added change_column_name migration helper function
- Added flake8 checks
- Added isort checks
- Added jsonb_change_key_name function expression
- Added jsonb substraction operator to support text data type
- Added remove_column migration helper


0.4.2 (2015-03-13)
^^^^^^^^^^^^^^^^^^

- Added data hybrid_property for Activity model. This property makes it easy to find all changes made in given record.


0.4.1 (2015-03-13)
^^^^^^^^^^^^^^^^^^

- Made client_addr overridable
- Removed client_port column from activity table (doesn't make sense in web environment)


0.4.0 (2015-03-12)
^^^^^^^^^^^^^^^^^^

- Added default value for audit_table exclude parameter
- Changed row_data and changed_fields types from HSTORE to JSONB
- Removed object_id column from activity table
- Renamed row_data to old_data and changed_fields to changed_data


0.3.0 (2015-02-24)
^^^^^^^^^^^^^^^^^^

- Added Flask extension
- Rewrote activity values setting. Now values are set after the flush phase occurs.


0.2.3 (2015-02-21)
^^^^^^^^^^^^^^^^^^

- Added explicit committing of audit_table ddl statements


0.2.2 (2015-02-21)
^^^^^^^^^^^^^^^^^^

- Made actor_id and actor properties of Activity model configured during mapper configuration phase


0.2.1 (2015-02-20)
^^^^^^^^^^^^^^^^^^

- Added audit_table function


0.2.0 (2015-02-19)
^^^^^^^^^^^^^^^^^^

- Added __versioned__ configuration parameter for models
- Added customizable column exclusion support for versioned models


0.1.7 (2015-02-18)
^^^^^^^^^^^^^^^^^^

- Removed foreign key from actor_id in Activity model


0.1.6 (2015-02-18)
^^^^^^^^^^^^^^^^^^

- Added support for callables as activity values
- Changed composite primary key separator from ',' to '|'


0.1.5 (2015-02-18)
^^^^^^^^^^^^^^^^^^

- Fixed pypi setup


0.1.4 (2015-02-18)
^^^^^^^^^^^^^^^^^^

- Made actor class and actor_id column customizable


0.1.3 (2015-02-17)
^^^^^^^^^^^^^^^^^^

- Made all file reads use absolute paths


0.1.2 (2015-02-17)
^^^^^^^^^^^^^^^^^^

- Removed all default indexes from activity table


0.1.1 (2015-02-17)
^^^^^^^^^^^^^^^^^^

- Added __repr__ for activity classes
- Removed session user name column from activity table
- Removed application name column from activity table


0.1 (2015-02-17)
^^^^^^^^^^^^^^^^

- Initial public release
