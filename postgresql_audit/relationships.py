import sqlalchemy as sa

from .expressions import ActivityReflector, ExpressionReflector


def s(value):
    return sa.text("'{0}'".format(value))


class RelationshipFetcher(object):
    def __init__(self, parent_activity):
        self.parent_activity = parent_activity
        self.mapper = sa.inspect(self.parent_activity.model_cls)

    def one_to_one_query(self, relationship):
        session = sa.orm.object_session(self.parent_activity)
        Activity = self.parent_activity.__class__
        return session.query(
            Activity
        ).filter(
            Activity.table_name == relationship.mapper.tables[0].name,
            Activity.transaction_id <= self.parent_activity.transaction_id,
            ExpressionReflector(
                Activity
            )(ActivityReflector(self.parent_activity)(
                relationship.primaryjoin)
            )
        ).order_by(Activity.transaction_id.desc()).limit(1)

    def one_to_many_query(self, relationship):
        session = sa.orm.object_session(self.parent_activity)
        Activity = self.parent_activity.__class__
        primaryjoin = ExpressionReflector(
            Activity
        )(ActivityReflector(self.parent_activity)(
            relationship.primaryjoin
        ))

        subquery = sa.select([
            Activity.data['id']
        ]).where(
            sa.and_(
                Activity.table_name == relationship.mapper.tables[0].name,
                Activity.transaction_id <= self.parent_activity.transaction_id,
                primaryjoin
            )
        ).alias('subquery')

        max_activity_ids_by_record = sa.select([
            Activity.data['id'],
            sa.func.max(Activity.id).label('id')
        ]).where(
            sa.and_(
                Activity.data['id'].in_(subquery),
                Activity.table_name == relationship.mapper.tables[0].name,
                Activity.transaction_id <= self.parent_activity.transaction_id,
            )
        ).group_by(Activity.data['id']).alias('grouped_activity_ids')

        return session.query(
            Activity
        ).filter(
            Activity.id.in_(
                sa.select(
                    [max_activity_ids_by_record.c.id],
                    from_obj=max_activity_ids_by_record
                )
            ),
            Activity.verb != 'delete',
            primaryjoin
        ).order_by(Activity.id)

    def correlate_primary_key(self, table, activity_alias, activity_alias2):
        return sa.and_(*[
            activity_alias.data[s(key)].astext ==
            activity_alias2.data[s(key)].astext
            for key in table.primary_key.columns.keys()
        ])

    def get_pks(self, table, activity):
        return [
            activity.data[s(key)]
            for key
            in table.primary_key.columns.keys()
        ]

    def association_exists_subquery(self, relationship, parent_activity):
        Activity = self.parent_activity.__class__
        aliased_activity = sa.orm.aliased(Activity)
        return (
            sa.select([sa.text('1')], from_obj=aliased_activity)
            .where(
                sa.and_(
                    aliased_activity.table_name ==
                    relationship.secondary.name,
                    self.correlate_primary_key(
                        relationship.secondary,
                        parent_activity,
                        aliased_activity
                    ),
                    aliased_activity.transaction_id <=
                    self.parent_activity.transaction_id,
                )
            ).group_by(
                *self.get_pks(
                    relationship.secondary,
                    aliased_activity
                )
            ).having(
                sa.func.max(aliased_activity.transaction_id) ==
                parent_activity.transaction_id
            )
        )



    def association_subquery(self, relationship):
        Activity = self.parent_activity.__class__
        aliased_activity = sa.orm.aliased(Activity)
        aliased_activity2 = sa.orm.aliased(Activity)
        primaryjoin = (
            ExpressionReflector(
                aliased_activity,
                lambda c: c.table == relationship.parent.tables[0]
            )(relationship.primaryjoin)
        )
        primaryjoin = ExpressionReflector(
             aliased_activity2,
             lambda c: c.table == relationship.secondary
        )(primaryjoin)

        secondaryjoin = ExpressionReflector(
            Activity, lambda c: c.table == relationship.mapper.tables[0]
        )(
            ExpressionReflector(
                aliased_activity2,
                lambda c: c.table == relationship.secondary
            )(relationship.secondaryjoin)
        )

        return sa.select(
            [sa.text('1')],
            from_obj=sa.inspect(
                aliased_activity
            ).selectable.join(
                sa.inspect(aliased_activity2).selectable,
                primaryjoin
            )
        ).where(
            sa.and_(
                aliased_activity2.table_name == relationship.secondary.name,
                secondaryjoin,
                sa.and_(*(
                    aliased_activity.data[s(key)].astext ==
                    str(self.parent_activity.data[key])
                    for key in
                    relationship.parent.tables[0].primary_key.columns.keys()
                )),
                aliased_activity2.verb != 'delete',
                sa.exists(
                    self.association_exists_subquery(
                        relationship,
                        aliased_activity2
                    )
                )
            )
        )

    def many_to_many_query(self, relationship):
        """
        Returns a query that fetches all activities objects for given
        relationship and given parent activity.
        """
        session = sa.orm.object_session(self.parent_activity)
        table_name = relationship.mapper.tables[0].name
        Activity = self.parent_activity.__class__
        aliased_activity4 = sa.orm.aliased(Activity)

        subquery = sa.select(
            [sa.text('1')],
            from_obj=aliased_activity4
        ).where(
            sa.and_(
                aliased_activity4.table_name == table_name,
                self.correlate_primary_key(
                    relationship.mapper.tables[0],
                    aliased_activity4,
                    Activity
                ),
                aliased_activity4.transaction_id <=
                self.parent_activity.transaction_id
            )
        ).group_by(
            *self.get_pks(relationship.mapper.tables[0], aliased_activity4)
        ).having(
            sa.func.max(aliased_activity4.transaction_id) ==
            Activity.transaction_id
        )

        query = session.query(
            Activity
        ).filter(
            Activity.table_name == table_name,
            sa.exists(self.association_subquery(relationship)),
            sa.exists(subquery),
            Activity.verb != 'delete',
        )
        return query

    def __getattr__(self, attr):
        relationship = self.mapper.relationships[attr]
        if relationship.secondary is not None:
            query = self.many_to_many_query(relationship)
        else:
            if not relationship.uselist:
                query = self.one_to_one_query(relationship)
            else:
                query = self.one_to_many_query(relationship)

        if relationship.uselist:
            return query.all()
        obj = query.first()
        if obj is None or obj.verb == 'delete':
            return None
        return obj
