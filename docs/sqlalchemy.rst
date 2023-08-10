SQLAlchemy integration
======================

SQLAlchemy_ integration offers easy way of using PostgreSQL-Audit with
SQLAlchemy ORM. It has the following features:

* Automatically marks all declarative classes, which have ``__versioned__``
  class property defined, as versioned.
* Attaches :meth:`~sqlalchemy.events.DDLEvents.after_create` DDL listeners that
  create versioning triggers for all versioned tables.
* Provides ``Activity`` model for easy ORM level access of activities.

.. _SQLAlchemy: https://www.sqlalchemy.org

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

You can easily exclude columns from being versioned by adding them as a list to
the ``'exclude'`` key of ``__versioned__`` dict::

    class Article(Base):
        __tablename__ = 'article'
        __versioned__ = {'exclude': 'created_at'}
        id = Column(Integer, primary_key=True)
        name = Column(String)
        created_at = Column(DateTime)


Versioning many-to-many tables
------------------------------

Versioning :class:`~sqlalchemy.schema.Table` objects is easy. Just call
``audit_table`` method with the desired table::

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


    versioning_manager.audit_table(group_user)


Tracking inserts
----------------

Now we can check the newly created activity::

    Activity = versioning_manager.activity_cls

    activity = Activity.query.first()
    activity.id             # 1
    activity.table_name     # 'article'
    activity.verb           # 'insert'
    activity.old_data       # {}
    activity.changed_data   # {'id': '1', 'name': 'Some article'}


Tracking updates
----------------

.. code-block:: python

    article.name = 'Some other article'
    session.commit()

    activity = Activity.query.order_by(db.desc(Activity.id)).first()
    activity.id             # 2
    activity.table_name     # 'article'
    activity.verb           # 'update'
    activity.old_data       # {'id': '1', 'name': 'Some article'}
    activity.changed_data   # {'name': 'Some other article'}


Tracking deletes
----------------

.. code-block:: python

    session.delete(article)
    session.commit()

    activity = Activity.query.order_by(db.desc(Activity.id)).first()
    activity.id             # 3
    activity.table_name     # 'article'
    activity.verb           # 'delete'
    activity.old_data       # {'id': '1', 'name': 'Some other article'}
    activity.changed_data   # {}


Finding history of specific record
----------------------------------

In this example, we want to find all changes made to an ``Article`` entity. The
query is a bit complex since we have to check ``old_data`` and ``changed_data``
separately. Luckily, the ``Activity`` model has a
:class:`~sqlalchemy.ext.hybrid.hybrid_property` called ``data`` which is a
combination of these two. Hence, you can get the desired activities as follows::

    activities = session.query(Activity).filter(
        Activity.table_name == 'article',
        Activity.data['id'].astext.cast(db.Integer) == 3
    )


Temporarily disabling inserts to the ``activity`` table
-------------------------------------------------------

There are cases where you might not want to track changes to your data, such as
when doing big changes to a table. In those cases, you can use the
``VersioningManager.disable`` context manager::

    with versioning_manager.disable(session):
        for i in range(1, 10000):
            db.session.add(db.Product(name='Product %s' % i))
        db.session.commit()
