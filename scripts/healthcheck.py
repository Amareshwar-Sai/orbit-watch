"""Wait up to 30 seconds for the disposable CI container to become ready."""

import http.client
import time

for attempt in range(30):
    connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=2)
    try:
        connection.request("GET", "/health")
        if connection.getresponse().status == 200:
            print("Container health endpoint passed")
            break
    except OSError:
        pass
    finally:
        connection.close()
    time.sleep(1)
else:
    raise SystemExit("Container did not become healthy")
