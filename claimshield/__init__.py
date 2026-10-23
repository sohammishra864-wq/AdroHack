try:
    import sqlite3  # noqa: F401
except ImportError:  # self-built Python without _sqlite3 (BIT HPC): use the pysqlite3 wheel instead
    import sys

    import pysqlite3

    sys.modules["sqlite3"] = pysqlite3
