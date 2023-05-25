from prometheus_client import start_http_server

import settings
from metrics import IbmiMetrics

_metrics_classes = [IbmiMetrics]

if __name__ == "__main__":
    start_http_server(settings.PROMETHEUS_CLIENT_PORT)
    while True:
        for metrics_cls in _metrics_classes:
            metrics_cls.get_instance().refresh()
