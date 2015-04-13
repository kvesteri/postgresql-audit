Migrations
==========

The schema of PostgreSQL-Audit is very flexible. Your schema can change without
the need of changing the version history schema. However it is recommended that you reflect
the changes you make to your schema to `old_data` and `changed_data` columns of audit.activity`
table.

Changing column name
--------------------

In a very common scenario you change a column name of an audited table. In order to avoid
situations where the activity data still contains references to old column names you need to
call :func:`.change_column_name` function in your alembic migration file.

::

    from postgresql_audit import change_column_name


    def upgrade():
        op.alter_column('my_table', 'my_column', new_column_name='some_column')

        change_column_name(op, 'my_table', 'my_column', 'some_column')

.. module:: postgresql_audit.base

.. autofunction:: change_column_name


Removing columns
----------------

.. autofunction:: remove_column


Adding columns
--------------

.. autofunction:: add_column


.. autoclass:: jsonb_merge

.. autoclass:: jsonb_change_key_name
