import sqlalchemy as sa
from sqlalchemy_utils import get_primary_keys

from .expressions import ExpressionReflector


class Resurrector(object):
    def resurrect(self, activity_cls, session, model, id):
        data = session.execute(
            self.resurrect_query(activity_cls, session, model, id)
        ).scalar()
        if data is None:
            return None
        obj = model(**data)
        session.add(obj)
        return obj

    def resurrect_all(self, activity_cls, session, model, expr):
        data = session.execute(
            self.resurrect_all_query(activity_cls, session, model, expr)
        ).fetchall()
        created_objects = []
        for row in data:
            obj = model(**row[0])
            session.add(obj)
            created_objects.append(obj)
        return created_objects

    def resurrect_query(self, activity_cls, session, model, id):
        if not isinstance(id, (list, tuple)):
            id = [id]
        return sa.select([activity_cls.data]).where(
            sa.and_(
                activity_cls.table_name == model.__tablename__,
                activity_cls.verb == 'delete',
                *(
                    activity_cls.data[column.name].astext ==
                    str(id[index])
                    for index, column
                    in enumerate(get_primary_keys(model).values())
                )
            )
        ).order_by(sa.desc(activity_cls.id)).limit(1)

    def resurrect_all_query(self, activity_cls, session, model, expr):
        reflected = ExpressionReflector(activity_cls)(expr)
        alias = sa.orm.aliased(activity_cls)
        return sa.select([activity_cls.data]).select_from(
            activity_cls.__table__.outerjoin(
                alias,
                sa.and_(
                    activity_cls.table_name == alias.table_name,
                    sa.and_(
                        activity_cls.data[c.name] == alias.data[c.name]
                        for c in get_primary_keys(model).values()
                    ),
                    activity_cls.issued_at < alias.issued_at
                )
            )
        ).where(
            sa.and_(
                alias.id.is_(None),
                reflected,
                activity_cls.verb == 'delete'
            )
        )
