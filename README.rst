PostgreSQL-Audit
================

Auditing extension for PostgreSQL. Provides additional extensions for SQLAlchemy and Flask.

Flask extension
---------------

.. code-block:: python


    from postgresql_audit.flask import versioning_manager

    from my_app.extensions import db


    versioning_manager.init(db.Model)


    class Article(db.Model):
        __tablename__ = 'article'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)


    article = Article(name='Some article')
    db.session.add(article)
    db.session.commit()



Now we can check the newly created activity.

.. code-block:: python

    Activity = versioning_manager.activity_cls

    activity = Activity.query.first()
    activity.id             # 1
    activity.table_name     # 'article'
    activity.verb           # 'insert'
    activity.object_id      # 1 (the newly generated article id)
    activity.row_data       # {'id': '1', 'name': 'Some article'}


.. code-block:: python

    article.name = 'Some other article'
    db.session.commit()

    activity = Activity.query.order_by(db.desc(Activity.id)).first()
    activity.id             # 2
    activity.table_name     # 'article'
    activity.verb           # 'update'
    activity.object_id      # 1
    activity.row_data       # {'id': '1', 'name': 'Some article'}
    activity.changed_fields # {'name': 'Some other article'}

