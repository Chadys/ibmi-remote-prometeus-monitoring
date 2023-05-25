import logging
from typing import Callable

import pyodbc
from prometheus_client import Enum, Gauge, Info

import settings
from connexion import IBMiConnection

logger = logging.getLogger(__name__)


class MetricsBase:
    NAMESPACE = ""
    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def __init__(self, *args, **kwargs):
        self.register()

    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        return metric_cls(
            name,
            documentation,
            labelnames=labelnames,
            namespace=self.NAMESPACE,
            **kwargs,
        )

    def register(self):
        raise NotImplementedError

    def refresh(self):
        raise NotImplementedError


class IbmiMetrics(MetricsBase):
    NAMESPACE = "ibmi"

    def register(self):
        self.system_status_up = self.register_metric(
            Gauge,
            "system_status_up",
            "System is up",
            labelnames=("server",),
        )
        self.info_metric = self.register_metric(
            Info,
            "ecosystem_environment",
            "Environment of the server",
            labelnames=("server",),
        )
        self.system_jobs_max = self.register_metric(
            Gauge,
            "system_jobs_max",
            "The maximum number of jobs that are allowed on the system",
            labelnames=("server",),
        )
        self.system_jobs_all_total = self.register_metric(
            Gauge,
            "system_jobs_all_total",
            "The total number of user and system jobs that are currently in the system",
            labelnames=("server",),
        )
        self.system_jobs_active_total = self.register_metric(
            Gauge,
            "system_jobs_active_total",
            "The total number of user and system active jobs in the system",
            labelnames=("server",),
        )
        self.system_jobs_batch_total = self.register_metric(
            Gauge,
            "system_jobs_batch_total",
            "The number of batch jobs currently running on the system",
            labelnames=("server",),
        )
        self.system_threads_total = self.register_metric(
            Gauge,
            "system_threads_total",
            "The number of initial and secondary threads in the system, including both user and system threads",
            labelnames=("server",),
        )
        self.system_cpu_usage_average_ratio = self.register_metric(
            Gauge,
            "system_cpu_usage_average_ratio",
            "Average CPU utilization for all of the active processors",
            labelnames=("server",),
        )
        self.system_cpu_nominal_average_ratio = self.register_metric(
            Gauge,
            "system_cpu_nominal_average_ratio",
            "CPU rate per nominal frequency",
            labelnames=("server",),
        )
        self.system_memory_capacity_bytes_total = self.register_metric(
            Gauge,
            "system_memory_capacity_bytes_total",
            "Total amount of memory on the system",
            labelnames=("server",),
        )
        self.system_storage_capacity_bytes = self.register_metric(
            Gauge,
            "system_storage_capacity_bytes",
            "The amount of storage in the system",
            labelnames=("server", "storage_type"),
        )
        self.system_storage_used_ratio = self.register_metric(
            Gauge,
            "system_storage_used_ratio",
            "The percentage of the storage currently in use",
            labelnames=("server", "storage_type"),
        )
        self.system_storage_address_used_ratio = self.register_metric(
            Gauge,
            "system_storage_address_used_ratio",
            "The percentage of the maximum possible addresses for objects that have been used",
            labelnames=("server", "object_type"),
        )

        self.remote_connections_total = self.register_metric(
            Gauge,
            "remote_connections_total",
            "Total number of  IPv4 and IPv6 network connections",
            labelnames=("server",),
        )

        self.http_server_connections_total = self.register_metric(
            Gauge,
            "http_server_connections_total",
            "Total number of connections to the server",
            labelnames=("server", "http_server", "http_function", "connections_type"),
        )
        self.http_server_requests_total = self.register_metric(
            Gauge,
            "http_server_requests_total",
            "Number of requests received",
            labelnames=("server", "http_server", "http_function"),
        )
        self.http_server_responses_total = self.register_metric(
            Gauge,
            "http_server_responses_total",
            "Number of responses sent",
            labelnames=("server", "http_server", "http_function"),
        )
        self.http_server_error_responses_total = self.register_metric(
            Gauge,
            "http_server_error_responses_total",
            "Number of error responses",
            labelnames=("server", "http_server", "http_function"),
        )
        self.http_server_bytes_total = self.register_metric(
            Gauge,
            "http_server_bytes_total",
            "Total number of bytes sent or received for all requests",
            labelnames=("server", "http_server", "http_function", "flow_direction"),
        )

        self.subsystem_status = self.register_metric(
            Enum,
            "subsystem_status",
            "The status of the subsystem",
            labelnames=("server", "subsystem"),
            states=["ACTIVE", "ENDING", "INACTIVE", "RESTRICTED", "STARTING"],
        )
        self.subsystem_jobs_active_total = self.register_metric(
            Gauge,
            "subsystem_jobs_active_total",
            "The number of jobs currently active in the subsystem",
            labelnames=("server", "subsystem"),
        )

        self.pool_storage_current_bytes = self.register_metric(
            Gauge,
            "pool_storage_current_bytes",
            "The amount of main storage, in the pool",
            labelnames=("server", "pool_name"),
        )
        self.pool_storage_reserved_bytes = self.register_metric(
            Gauge,
            "pool_storage_reserved_bytes",
            "The amount of storage, in the pool reserved for system use (for example, for save/restore operations).",
            labelnames=("server", "pool_name"),
        )
        self.pool_threads_total = self.register_metric(
            Gauge,
            "pool_threads_total",
            "The number of threads currently using the pool",
            labelnames=("server", "pool_name"),
        )
        self.total_memory = None

    def refresh(self):
        for db_name, db_settings in settings.DATABASES.items():
            if db_name.startswith("ibmi"):
                logger.info(f"refreshing metrics for {db_name}")
                self.update_country_monitoring(db_name, db_settings)

    def _set_gauge(
        self,
        gauge: Gauge,
        row: dict,
        key: str,
        labels: dict,
        func: Callable[[float], float] = lambda x: x,
    ):
        value = row.get(key, None)
        if value is not None:
            gauge.labels(**labels).set(func(value))

    def fill_info_metrics(self, connection: pyodbc.Connection, db_name: str):
        language_feature_code = ""

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM SYSIBMADM.ENV_SYS_INFO")
            env_row = dict(
                zip((column[0] for column in cursor.description), cursor.fetchone())
            )
            # convert from megabytes to bytes
            self.total_memory = env_row["TOTAL_MEMORY"] * 1000000
            os_version = f"V{env_row['OS_VERSION']}R{env_row['OS_RELEASE']}"
            host_name = env_row["HOST_NAME"]
            try:
                # Get more precise version string for OS that support it
                cursor.execute(
                    "SELECT DATA_AREA_VALUE FROM "
                    "TABLE(QSYS2.DATA_AREA_INFO(DATA_AREA_LIBRARY=>'QUSRSYS',DATA_AREA_NAME=>'QSS1MRI')) X"
                )
                os_version, language_feature_code = cursor.fetchval().split()
            except pyodbc.ProgrammingError as e:
                # before V7R3 there is no DATA_AREA_INFO
                logger.debug(e)
            # Here you can add specific software version info using DATA_AREA_INFO
            # else:
            #   TODO add specific software version info

        self.info_metric.labels(**{"server": db_name}).info(
            {
                "database_name": connection.getinfo(pyodbc.SQL_DATABASE_NAME),
                "dbms_product": connection.getinfo(pyodbc.SQL_DBMS_NAME),
                "dbms_version": connection.getinfo(pyodbc.SQL_DBMS_VER),
                "server_name": connection.getinfo(pyodbc.SQL_SERVER_NAME),
                "host_name": host_name,
                "os_version": os_version,
                "language_feature_code": language_feature_code,  # https://www.ibm.com/docs/en/i/7.5?topic=reference-feature-codes-language-version
                # "software1_version": software1_version,
            }
        )

    def fill_system_metrics(self, connection: pyodbc.Connection, db_name: str):
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT * FROM TABLE(QSYS2.SYSTEM_STATUS(RESET_STATISTICS=>'YES',DETAILED_INFO=>'ALL')) X"
                )
            except pyodbc.Error as e:
                # before V7R3 there is no DETAILED_INFO parameter
                logger.debug(e)
                cursor.execute(
                    "SELECT * FROM TABLE(QSYS2.SYSTEM_STATUS(RESET_STATISTICS=>'YES')) X"
                )
            row = dict(
                zip((column[0] for column in cursor.description), cursor.fetchone())
            )
        self._set_gauge(
            self.system_jobs_max,
            row,
            "MAXIMUM_JOBS_IN_SYSTEM",
            labels={"server": db_name},
        )
        self._set_gauge(
            self.system_jobs_all_total,
            row,
            "TOTAL_JOBS_IN_SYSTEM",
            labels={"server": db_name},
        )
        self._set_gauge(
            self.system_jobs_active_total,
            row,
            "ACTIVE_JOBS_IN_SYSTEM",
            labels={"server": db_name},
        )
        self._set_gauge(
            self.system_jobs_batch_total,
            row,
            "BATCH_RUNNING",
            labels={"server": db_name},
        )
        self._set_gauge(
            self.system_threads_total,
            row,
            "ACTIVE_THREADS_IN_SYSTEM",
            labels={"server": db_name},
        )
        # convert from megabytes to bytes
        self.system_memory_capacity_bytes_total.labels(**{"server": db_name}).set(
            self.total_memory
        )
        # convert from kilobytes to bytes
        self._set_gauge(
            self.system_storage_capacity_bytes,
            row,
            "MAIN_STORAGE_SIZE",
            labels={"server": db_name, "storage_type": "main"},
            func=lambda x: x * 1000,
        )
        # convert from megabytes to bytes
        self._set_gauge(
            self.system_storage_capacity_bytes,
            row,
            "SYSTEM_ASP_STORAGE",
            labels={"server": db_name, "storage_type": "asp"},
            func=lambda x: x * 1000000,
        )
        # convert from megabytes to bytes
        self._set_gauge(
            self.system_storage_capacity_bytes,
            row,
            "TOTAL_AUXILIARY_STORAGE",
            labels={"server": db_name, "storage_type": "auxiliary"},
            func=lambda x: x * 1000000,
        )
        # convert from 0-100 ratio to 0-1
        self._set_gauge(
            self.system_storage_used_ratio,
            row,
            "SYSTEM_ASP_USED",
            labels={"server": db_name, "storage_type": "asp"},
            func=lambda x: x / 100,
        )
        self._set_gauge(
            self.system_storage_used_ratio,
            row,
            "CURRENT_TEMPORARY_STORAGE",
            labels={"server": db_name, "storage_type": "auxiliary"},
            func=lambda x: x / row["TOTAL_AUXILIARY_STORAGE"],
        )
        # convert from 0-100 ratio to 0-1
        self._set_gauge(
            self.system_storage_address_used_ratio,
            row,
            "PERMANENT_ADDRESS_RATE",
            labels={"server": db_name, "object_type": "permanent"},
            func=lambda x: x / 100,
        )
        # convert from 0-100 ratio to 0-1
        self._set_gauge(
            self.system_storage_address_used_ratio,
            row,
            "TEMPORARY_ADDRESS_RATE",
            labels={"server": db_name, "object_type": "temporary"},
            func=lambda x: x / 100,
        )
        try:
            # since V7R3, "AVERAGE_CPU_RATE" is always 0 in SYSTEM_STATUS, we need to use SYSTEM_ACTIVITY_INFO instead
            cursor.execute("SELECT * FROM TABLE(QSYS2.SYSTEM_ACTIVITY_INFO())")
        except pyodbc.ProgrammingError as e:
            # before V7R3, we can keep reading the values in SYSTEM_STATUS
            logger.debug(e)
        else:
            row = dict(
                zip((column[0] for column in cursor.description), cursor.fetchone())
            )
        # convert from 0-100 ratio to 0-1
        self._set_gauge(
            self.system_cpu_nominal_average_ratio,
            row,
            "AVERAGE_CPU_RATE",
            labels={"server": db_name},
            func=lambda x: x / 100,
        )
        # convert from 0-100 ratio to 0-1
        self._set_gauge(
            self.system_cpu_usage_average_ratio,
            row,
            "AVERAGE_CPU_UTILIZATION",
            labels={"server": db_name},
            func=lambda x: x / 100,
        )

    def fill_net_metrics(self, connection: pyodbc.Connection, db_name: str):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(REMOTE_ADDRESS) AS REMOTE_CONNECTIONS FROM QSYS2.NETSTAT_INFO WHERE TCP_STATE = 'ESTABLISHED' AND REMOTE_ADDRESS != '::1' AND REMOTE_ADDRESS != '127.0.0.1'"
            )
            remote_connections_count = cursor.fetchval()

        self.remote_connections_total.labels(**{"server": db_name}).set(
            remote_connections_count
        )

    def fill_http_metrics(self, connection: pyodbc.Connection, db_name: str):
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT * FROM QSYS2.HTTP_SERVER_INFO")
            except pyodbc.ProgrammingError as e:
                # before V7R3 there is no HTTP_SERVER_INFO
                logger.debug(e)
            else:
                for row in cursor:
                    row = dict(zip((column[0] for column in cursor.description), row))

                    self._set_gauge(
                        self.http_server_connections_total,
                        row,
                        "SERVER_NORMAL_CONNECTIONS",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                            "connections_type": "normal",
                        },
                    )
                    self._set_gauge(
                        self.http_server_connections_total,
                        row,
                        "SERVER_SSL_CONNECTIONS",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                            "connections_type": "ssl",
                        },
                    )
                    self._set_gauge(
                        self.http_server_requests_total,
                        row,
                        "REQUESTS",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                        },
                    )
                    self._set_gauge(
                        self.http_server_responses_total,
                        row,
                        "RESPONSES",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                        },
                    )
                    self._set_gauge(
                        self.http_server_error_responses_total,
                        row,
                        "ERROR_RESPONSES",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                        },
                    )
                    self._set_gauge(
                        self.http_server_bytes_total,
                        row,
                        "BYTES_SENT",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                            "flow_direction": "sent",
                        },
                    )
                    self._set_gauge(
                        self.http_server_bytes_total,
                        row,
                        "BYTES_RECEIVED",
                        labels={
                            "server": db_name,
                            "http_server": row["SERVER_NAME"],
                            "http_function": row["HTTP_FUNCTION"],
                            "flow_direction": "received",
                        },
                    )

    def fill_subsystem_metrics(self, connection: pyodbc.Connection, db_name: str):
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT * FROM QSYS2.SUBSYSTEM_INFO")
            except pyodbc.ProgrammingError as e:
                # before V7R3 there is no SUBSYSTEM_INFO
                logger.debug(e)
            else:
                for row in cursor:
                    row = dict(zip((column[0] for column in cursor.description), row))

                    self.subsystem_status.labels(
                        **{"server": db_name, "subsystem": row["SUBSYSTEM_DESCRIPTION"]}
                    ).state(row["STATUS"])

                    self._set_gauge(
                        self.subsystem_jobs_active_total,
                        row,
                        "CURRENT_ACTIVE_JOBS",
                        labels={
                            "server": db_name,
                            "subsystem": row["SUBSYSTEM_DESCRIPTION"],
                        },
                    )

    def fill_memory_pool_metrics(self, connection: pyodbc.Connection, db_name: str):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM QSYS2.MEMORY_POOL_INFO")
            for row in cursor:
                row = dict(zip((column[0] for column in cursor.description), row))
                pool_name = row["POOL_NAME"].strip()

                # convert from megabytes to bytes
                self._set_gauge(
                    self.pool_storage_current_bytes,
                    row,
                    "CURRENT_SIZE",
                    labels={"server": db_name, "pool_name": pool_name},
                    func=lambda x: x * 1000000,
                )
                # convert from megabytes to bytes
                self._set_gauge(
                    self.pool_storage_reserved_bytes,
                    row,
                    "RESERVED_SIZE",
                    labels={"server": db_name, "pool_name": pool_name},
                    func=lambda x: x * 1000000,
                )
                self._set_gauge(
                    self.pool_threads_total,
                    row,
                    "CURRENT_THREADS",
                    labels={"server": db_name, "pool_name": pool_name},
                )

    def update_country_monitoring(self, db_name: str, db_settings: dict):
        logger.debug(f"{db_name}: start")
        try:
            with IBMiConnection.managed_connection(
                db_settings,
                readonly=True,
            ) as connection:
                logger.debug(f"{db_name}: connected")
                self.fill_info_metrics(connection, db_name)
                logger.debug(f"{db_name}: info")
                self.fill_system_metrics(connection, db_name)
                logger.debug(f"{db_name}: system")
                self.fill_net_metrics(connection, db_name)
                logger.debug(f"{db_name}: net")
                self.fill_subsystem_metrics(connection, db_name)
                logger.debug(f"{db_name}: subsystem")
                self.fill_http_metrics(connection, db_name)
                logger.debug(f"{db_name}: http")
                self.fill_memory_pool_metrics(connection, db_name)
                logger.debug(f"{db_name}: pool")
                self.system_status_up.labels(server=db_name).set(1)
        except pyodbc.OperationalError as e:
            logger.debug(f"{db_name}: timeout {e}")
            self.system_status_up.labels(server=db_name).set(0)
