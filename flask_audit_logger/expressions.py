from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression


class jsonb_change_key_name(expression.FunctionElement):
    """Provides jsonb_change_key_name as a SQLAlchemy FunctionElement."""

    type = JSONB()
    name = "jsonb_change_key_name"
    inherit_cache = False


@compiles(jsonb_change_key_name)
def compile_jsonb_change_key_name(element, compiler, **kw):
    arg1, arg2, arg3 = list(element.clauses)
    arg1.type = JSONB()
    return "jsonb_change_key_name({0}, {1}, {2})".format(
        compiler.process(arg1), compiler.process(arg2), compiler.process(arg3)
    )
