SQLAlchemy integration
======================



.. code-block:: python


    from postgresql_audit import versioning_manager


    versioning_manager.init(Base)


    class Article(Base):
        __tablename__ = 'article'
        id = Column(Integer, primary_key=True)
        name = Column(String)


    article = Article(name='Some article')
    session.add(article)
    session.commit()


Tracking inserts
----------------

Now we can check the newly created activity.

.. code-block:: python

    Activity = versioning_manager.activity_cls

    activity = Activity.query.first()
    activity.id             # 1
    activity.table_name     # 'article'
    activity.verb           # 'insert'
    activity.object_id      # 1 (the newly generated article id)
    activity.row_data       # {'id': '1', 'name': 'Some article'}


Tracking updates
----------------


.. code-block:: python

    article.name = 'Some other article'
    session.commit()

    activity = Activity.query.order_by(db.desc(Activity.id)).first()
    activity.id             # 2
    activity.table_name     # 'article'
    activity.verb           # 'update'
    activity.object_id      # 1
    activity.row_data       # {'id': '1', 'name': 'Some article'}
    activity.changed_fields # {'name': 'Some other article'}


Tracking deletes
----------------


.. code-block:: python

    session.delete(article)
    session.commit()

    activity = Activity.query.order_by(db.desc(Activity.id)).first()
    activity.id             # 3
    activity.table_name     # 'article'
    activity.verb           # 'delete'
    activity.object_id      # 1
    activity.row_data       # {'id': '1', 'name': 'Some other article'}
