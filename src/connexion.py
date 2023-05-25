from contextlib import contextmanager

import pyodbc


class IBMiConnection:
    @staticmethod
    def create_connection(db_settings, **kwargs) -> pyodbc.Connection:
        return pyodbc.connect(
            driver="{IBM i Access ODBC Driver}",
            SYSTEM=db_settings["HOST"],
            UID=db_settings["USER"],
            PWD=db_settings["PASSWORD"],
            SSL=1 if db_settings["OPTIONS"].get("sslmode") == "require" else 0,
            DATABASE=db_settings["NAME"],
            **kwargs,
        )

    @classmethod
    @contextmanager
    def managed_connection(cls, db_settings, **kwargs) -> pyodbc.Connection:
        # pyodbc.connect contextmanager calls connection.commit and not connection.close when leaving the context
        connection = cls.create_connection(db_settings, **kwargs)
        try:
            yield connection
        finally:
            connection.close()
