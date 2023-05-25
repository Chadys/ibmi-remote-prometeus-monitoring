import urllib.parse as urlparse
from typing import Any, Dict, Optional, TypedDict, Union


# From https://github.com/jazzband/dj-database-url/blob/master/dj_database_url/__init__.py
class DBConfig(TypedDict, total=False):
    ATOMIC_REQUESTS: bool
    AUTOCOMMIT: bool
    CONN_MAX_AGE: Optional[int]
    CONN_HEALTH_CHECKS: bool
    DISABLE_SERVER_SIDE_CURSORS: bool
    ENGINE: str
    HOST: str
    NAME: str
    OPTIONS: Optional[Dict[str, Any]]
    PASSWORD: str
    PORT: Union[str, int]
    TEST: Dict[str, Any]
    TIME_ZONE: str
    USER: str


def ibmi_db_url_parse(
    url: str,
    conn_max_age: Optional[int] = 0,
    conn_health_checks: bool = False,
    ssl_require: bool = False,
    test_options: Optional[dict] = None,
) -> DBConfig:
    """
    Simplified version of dj_database_url.parse that only handle ibmi url
    """
    parsed_config: DBConfig = {}
    if test_options is None:
        test_options = {}

    spliturl = urlparse.urlsplit(url)

    # Split query strings from path.
    path = spliturl.path[1:]
    query = urlparse.parse_qs(spliturl.query)

    # Update with environment configuration.
    parsed_config.update(
        {
            "NAME": urlparse.unquote(path or ""),
            "USER": urlparse.unquote(spliturl.username or ""),
            "PASSWORD": urlparse.unquote(spliturl.password or ""),
            "HOST": spliturl.hostname or "",
            "PORT": spliturl.port or "",
            "CONN_MAX_AGE": conn_max_age,
            "CONN_HEALTH_CHECKS": conn_health_checks,
        }
    )
    if test_options:
        parsed_config.update(
            {
                "TEST": test_options,
            }
        )

    # Pass the query string into OPTIONS.
    options: Dict[str, Any] = {}
    for key, values in query.items():
        options[key] = values[-1]

    if ssl_require:
        options["sslmode"] = "require"

    if options:
        parsed_config["OPTIONS"] = options

    return parsed_config
