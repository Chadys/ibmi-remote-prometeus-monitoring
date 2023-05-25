import logging

from environs import Env

from utils import ibmi_db_url_parse

env = Env()

PROMETHEUS_CLIENT_PORT = env.int("PROMETHEUS_CLIENT_PORT", default=8000)

LOGLEVEL = env.str("LOGLEVEL", default="WARNING").upper()

DATABASES = {}
IBMI_SSL = env.bool("IBMI_SSL", default=True)
_ibmi_db: dict = env.dict("IBMI_DB_URL")
for _ibmi_label, _ibmi_db in _ibmi_db.items():
    DATABASES[f"ibmi_{_ibmi_label}"] = ibmi_db_url_parse(_ibmi_db, ssl_require=IBMI_SSL)

logging.basicConfig(
    level=LOGLEVEL,
    format="[{levelname}] <{asctime}> {pathname}:{lineno} {message}",
    style="{",
)
