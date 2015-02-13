def last_activity(connection):
    return dict(
        connection.execute(
            'SELECT * FROM audit.activity ORDER BY issued_at DESC LIMIT 1'
        ).fetchone()
    )
