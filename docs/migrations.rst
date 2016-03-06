Migrations
==========

Usually your schema changes over time. The schema of PostgreSQL-Audit is very flexible, since it stores the data in JSONB columns. Your schema can change without the need of changing the version history JSONB data columns.

However in case you want to show the version history on the application side you may want to reflect the changes you make to your schema to `old_data` and `changed_data` columns of `activity` table. The other solution is to make your application code aware of all the schema changes that have happened over time. This can get a bit tedious if your schema is quickly evolving.


Changing column name
--------------------

.. module:: postgresql_audit.migrations

.. autofunction:: change_column_name


Alter column type
-----------------

.. autofunction:: alter_column


Removing columns
----------------

.. autofunction:: remove_column


Adding columns
--------------

.. autofunction:: add_column


.. autoclass:: jsonb_merge

.. autoclass:: jsonb_change_key_name


Rename table
------------

.. autofunction:: rename_table
