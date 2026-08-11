"""
Compile-time / local-dev defaults for integrations.

Persisted overrides live in ``storage.config.AppConfig`` (written to
``config.json`` under the data root). Values here seed those defaults when a
field is missing from disk — they are not a second config system.
"""

LEDFX_HOST = "127.0.0.1"
LEDFX_PORT = 8888
LEDFX_BASE_URL = f"http://{LEDFX_HOST}:{LEDFX_PORT}"

LEDFX_ENABLED = False
LEDFX_SCENE_REFRESH_S = 25.0
LEDFX_REQUEST_TIMEOUT_S = 2.0
