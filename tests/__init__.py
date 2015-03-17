try:
    import __pypy__
except ImportError:
    __pypy__ = None


if __pypy__:
    from psycopg2cffi import compat
    compat.register()
