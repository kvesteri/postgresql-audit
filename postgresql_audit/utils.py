import os
import string

import sqlalchemy as sa

HERE = os.path.dirname(os.path.abspath(__file__))


class StatementExecutor(object):
    def __init__(self, stmt):
        self.stmt = stmt

    def __call__(self, target, bind, **kwargs):
        tx = bind.begin()
        bind.execute(self.stmt)
        tx.commit()


def read_file(file_):
    with open(os.path.join(HERE, file_)) as f:
        s = f.read()
    return s


def render_tmpl(tmpl_name, schema_name=None):
    file_contents = read_file(
        'templates/{}'.format(tmpl_name)
    ).replace('%', '%%').replace('$$', '$$$$')
    tmpl = string.Template(file_contents)
    context = dict(schema_name=schema_name)

    if schema_name is None:
        context['schema_prefix'] = ''
        context['revoke_cmd'] = ''
    else:
        context['schema_prefix'] = '{}.'.format(schema_name)
        context['revoke_cmd'] = (
            'REVOKE ALL ON {schema_prefix}activity FROM public;'
        ).format(**context)

    return tmpl.substitute(**context)


def create_operators(target, bind, schema_name, **kwargs):
    if bind.dialect.server_version_info < (9, 5, 0):
        StatementExecutor(render_tmpl('operators_pre95.sql', schema_name))(
            target, bind, **kwargs
        )
    if bind.dialect.server_version_info < (9, 6, 0):
        StatementExecutor(render_tmpl('operators_pre96.sql', schema_name))(
            target, bind, **kwargs
        )
    if bind.dialect.server_version_info < (10, 0):
        operators_template = render_tmpl('operators_pre100.sql', schema_name)
        StatementExecutor(operators_template)(target, bind, **kwargs)
    operators_template = render_tmpl('operators.sql', schema_name)
    StatementExecutor(operators_template)(target, bind, **kwargs)


def create_audit_table(
    target, bind, schema_name, use_statement_level_triggers, **kwargs
):
    sql = ''
    if (
        use_statement_level_triggers and
        bind.dialect.server_version_info >= (10, 0)
    ):
        sql += render_tmpl('create_activity_stmt_level.sql', schema_name)
        sql += render_tmpl('audit_table_stmt_level.sql', schema_name)
    else:
        sql += render_tmpl('create_activity_row_level.sql', schema_name)
        sql += render_tmpl('audit_table_row_level.sql', schema_name)
    StatementExecutor(sql)(target, bind, **kwargs)


def build_register_table_query(schema_name, *args):
    if schema_name is None:
        func = sa.func.audit_table
    else:
        func = getattr(getattr(sa.func, schema_name), 'audit_table')
    return sa.select([func(*args)])
