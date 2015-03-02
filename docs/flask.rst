Flask extension
---------------

Flask extension provides means for easy integration with PostgreSQL-Audit, Flask-Login
and Flask-SQLAlchemy. By default the Flask extensions tries to get the current user
from Flask-Login and assigns the id of this object as the actor_id of all activities in given transaction. It also assigns the current user ip address to all present activities.


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
