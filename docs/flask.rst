Flask extension
===============

Flask extension provides means for easy integration with PostgreSQL-Audit, Flask-Login
and Flask-SQLAlchemy. It provides all the goodies that SQLAlchemy integration provides along with:

* By default the Flask extensions tries to get the current user from Flask-Login and assigns the id of this object as the actor_id of all activities in given transaction. It also assigns the current user ip address to all present activities.
* Easy overriding of current activity values using activity_values context manager

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

In some situations you may want to override the current activity values. One scenario
is where you want to track changes to associated objects and mark those changes with
target_id property of Activity model.

Consider for example the following model structure with Articles and Tags. Let's say
we want to show the changelog of an article that contains all changes to this article and its tags.

.. code-block:: python


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

When tracking the changes to article we don't need any changes.

.. code-block:: python

    article = Article(name='Some article')
    db.session.add(article)
    db.session.commit()


When adding tags we need to make the generated activities use the article id as the target_id, so that we can track them later on.


.. code-block:: python

    from postgresql_audit.flask import activity_values


    with activity_values(target_id=str(article.id)):
        article.tags = [Tag(name='Some tag')]
        db.session.commit()


Now we can find all activities for given article with the following query.

.. code-block:: python


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

__ http://flask.pocoo.org/docs/0.10/deploying/wsgi-standalone/#proxy-setups
