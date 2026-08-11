"""Application defaults. Edit host and port here for local development."""

LEDFX_HOST = "127.0.0.1"
LEDFX_PORT = 8888
LEDFX_BASE_URL = f"http://{LEDFX_HOST}:{LEDFX_PORT}"

LEDFX_ENABLED = False
LEDFX_SCENE_REFRESH_S = 25.0
LEDFX_REQUEST_TIMEOUT_S = 2.0
