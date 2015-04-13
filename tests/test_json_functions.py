import pytest
import sqlalchemy as sa

from postgresql_audit import jsonb_change_key_name, jsonb_merge


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestJSONBChangeKeyName(object):
    @pytest.mark.parametrize(
        ('data', 'old_key', 'new_key', 'expected'),
        (
            (
                '{"key1": 4, "key2": 3}',
                'key1',
                'key3',
                {"key3": 4, "key2": 3}
            ),
            (
                '{"key1": 4}',
                'key2',
                'key3',
                {"key1": 4}
            ),
            (
                '{"key1": 4, "key2": 3}',
                'key1',
                'key2',
                {"key2": 3}
            ),
        )
    )
    def test_raw_sql(self, session, data, old_key, new_key, expected):
        result = session.execute(
            '''SELECT jsonb_change_key_name(
                '{data}'::jsonb,
                '{old_key}',
                '{new_key}'
            )'''.format(
                data=data,
                old_key=old_key,
                new_key=new_key
            )
        ).scalar()
        assert result == expected

    @pytest.mark.parametrize(
        ('data', 'old_key', 'new_key', 'expected'),
        (
            (
                {"key1": 4, "key2": 3},
                'key1',
                'key3',
                {"key3": 4, "key2": 3}
            ),
            (
                {"key1": 4},
                'key2',
                'key3',
                {"key1": 4}
            ),
            (
                {"key1": 4, "key2": 3},
                'key1',
                'key2',
                {"key2": 3}
            ),
        )
    )
    def test_sqlalchemy_function_expr(
        self,
        session,
        data,
        old_key,
        new_key,
        expected
    ):
        result = session.execute(
            sa.select([jsonb_change_key_name(data, old_key, new_key)])
        ).scalar()
        assert result == expected


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestJSONBMerge(object):
    @pytest.mark.parametrize(
        ('data', 'merge_data', 'expected'),
        (
            (
                '{"key1": 4, "key2": 3}',
                '{"key1": 5, "key3": 5}',
                {"key1": 5, "key2": 3, "key3": 5}
            ),
            (
                '{}',
                '{"key1": 5, "key3": 5}',
                {"key1": 5, "key3": 5}
            ),
            (
                '{"key1": 4, "key2": 3}',
                '{}',
                {"key1": 4, "key2": 3}
            ),
        )
    )
    def test_raw_sql(self, session, data, merge_data, expected):
        result = session.execute(
            '''SELECT jsonb_merge(
                '{data}'::jsonb,
                '{merge_data}'::jsonb
            )'''.format(
                data=data,
                merge_data=merge_data
            )
        ).scalar()
        assert result == expected

    @pytest.mark.parametrize(
        ('data', 'merge_data', 'expected'),
        (
            (
                {"key1": 4, "key2": 3},
                {"key1": 5, "key3": 5},
                {"key1": 5, "key2": 3, "key3": 5}
            ),
            (
                {},
                {"key1": 5, "key3": 5},
                {"key1": 5, "key3": 5}
            ),
            (
                {"key1": 4, "key2": 3},
                {},
                {"key1": 4, "key2": 3}
            ),
        )
    )
    def test_sqlalchemy_function_expr(
        self,
        session,
        data,
        merge_data,
        expected
    ):
        result = session.execute(
            sa.select([jsonb_merge(data, merge_data)])
        ).scalar()
        assert result == expected
