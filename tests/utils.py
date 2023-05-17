from sqlalchemy import text


def last_activity(connection, schema=None):
    if schema is not None:
        schema_prefix = '{}.'.format(schema)
    else:
        schema_prefix = ''
    return connection.execute(
        text(
            'SELECT * FROM {}activity ORDER BY issued_at '
            'DESC LIMIT 1'.format(schema_prefix)
        )
    ).mappings().fetchone()
