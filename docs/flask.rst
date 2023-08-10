Flask extension
===============

Flask_ extension provides means for easy integration with PostgreSQL-Audit,
Flask-Login_ and Flask-SQLAlchemy_. It provides all the goodies that SQLAlchemy
integration provides along with:

* By default, the Flask extensions tries to get the current user from
  Flask-Login and assigns the id of this object as the ``actor_id`` of all
  activities in given transaction. It also assigns the current user's IP address
  to all present activities.

* Easy overriding of current activity values using ``activity_values`` context
  manager

.. _Flask: https://flask.palletsprojects.com/
.. _Flask-Login: https://flask-login.readthedocs.io/
.. _Flask-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/

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


Overriding activity values
--------------------------

In some situations you may want to override the current activity values. One
scenario is where you want to track the changes to associated objects and mark
those changes with the ``target_id`` property of the ``Activity`` model.

For example, consider the following model structure with ``Article`` and
``Tag``. Let's say we want to show the changelog of an article that contains all
changes to this article and its tags::

    from postgresql_audit.flask import versioning_manager

    from my_app.extensions import db


    versioning_manager.init(db.Model)


    class Article(db.Model):
        __tablename__ = 'article'
        __versioned__ = {}
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)


    class Tag(db.Model):
        __tablename__ = 'tag'
        __versioned__ = {}
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        article_id = db.Column(
            db.Integer,
            db.ForeignKey(Article.id, ondelete='CASCADE')
        )
        article = db.relationship(Article, backref='tags')

When tracking the changes to article, we don't need any changes::

    article = Article(name='Some article')
    db.session.add(article)
    db.session.commit()

When adding tags, we need to make the generated activities use the article id as
the ``target_id`` so that we can track them later on::

    from postgresql_audit.flask import activity_values


    with activity_values(target_id=str(article.id)):
        article.tags = [Tag(name='Some tag')]
        db.session.commit()

Now, we can find all activities for an article with the following query::

    Activity = versioning_manager.activity_cls

    activities = Activity.query.filter(
        db.or_(
            db.and_(
                Activity.target_id == str(article.id),
                Activity.target_table_name == 'article'
            ),
            db.and_(
                db.or_(
                    Activity.row_data['id'] == article.id,
                    Activity.changed_fields['id'] == article.id
                ),
                Activity.table_name == 'article'
            )
        )
    ).order_by(Activity.issued_at)


Recording IP address behind proxy
---------------------------------

By default PostgreSQL-Audit stores the client address as found in the request
and does not attempt to make assumptions on server proxy configuration.
Thus, in case the flask app runs after an http server (e.g nginx), and
depending on configuration, flask may receive no IP. To overcome this, it is
advised to follow `flask documentation on proxy setups`__.

__ https://flask.palletsprojects.com/en/1.1.x/deploying/wsgi-standalone/#proxy-setups
