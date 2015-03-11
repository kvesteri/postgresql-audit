Changelog
---------

Here you can see the full list of changes between each PostgreSQL-Audit release.


0.4.0 (2015-xx-xx)
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
