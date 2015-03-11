SQLAlchemy integration
======================


SQLAlchemy integration offers easy way of using PostgreSQL-Audit with SQLAlchemy ORM. It has the following features:

* Automatically marks all declarative classes which have `__versioned__` class property defined as versioned.
* Attaches after_create DDL listeners that create versioning triggers for all versioned tables.
* Provides Activity model for easy ORM level access of activities


.. code-block:: python


    from postgresql_audit import versioning_manager


    versioning_manager.init(Base)


    class Article(Base):
        __tablename__ = 'article'
        __versioned__ = {}
        id = Column(Integer, primary_key=True)
        name = Column(String)


    article = Article(name='Some article')
    session.add(article)
    session.commit()


Excluding columns
-----------------

You can easily exclude columns from being versioned by adding them as a list to 'exclude' key of `__versioned__` dict.

.. code-block:: python

    class Article(Base):
        __tablename__ = 'article'
        __versioned__ = {'exclude': 'created_at'}
        id = Column(Integer, primary_key=True)
        name = Column(String)
        created_at = Column(DateTime)


Versioning many-to-many tables
------------------------------

Versioning Table objects is easy. Just call audit_table function with the desired table.

.. code-block:: python

    from postgresql_audit import audit_table


    class User(Base):
        __tablename__ = 'user'
        __versioned__ = {}
        id = Column(Integer, primary_key=True)
        name = Column(String)

    class Group(Base):
        __tablename__ = 'group'
        __versioned__ = {}
        id = Column(Integer, primary_key=True)
        name = Column(String)


    group_user = Table(
        'group_user',
        Base.metadata,
        Column(
            'user_id',
            Integer,
            ForeignKey('user.id', ondelete='CASCADE'),
            nullable=False,
            primary_key=True
        ),
        Column(
            'group_id',
            Integer,
            ForeignKey('place.id', ondelete='CASCADE'),
            nullable=False,
            primary_key=True
        )


    audit_table(group_user)


Tracking inserts
----------------

Now we can check the newly created activity.

.. code-block:: python

    Activity = versioning_manager.activity_cls

    activity = Activity.query.first()
    activity.id             # 1
    activity.table_name     # 'article'
    activity.verb           # 'insert'
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
    activity.row_data       # {'id': '1', 'name': 'Some other article'}
