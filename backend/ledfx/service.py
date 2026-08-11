from __future__ import annotations

from typing import Optional, Tuple

from ledfx.client import LedFxClient, LedFxClientProtocol, NullLedFxClient
from ledfx.scene_sync import LedFxSceneSync
from storage.config import LedfxConfig
from storage.library import Library


def build_ledfx_stack(
    library: Library,
    config: Optional[LedfxConfig] = None,
) -> Tuple[LedFxClientProtocol, Optional[LedFxSceneSync]]:
    """
    Construct the LEDfx client and optional scene sync from config.

    When ``enabled`` is false, returns a ``NullLedFxClient`` and no sync loop.
    """
    cfg = config if config is not None else library.config.ledfx
    if not cfg.enabled:
        return NullLedFxClient(), None

    client = LedFxClient(
        base_url=cfg.base_url,
        timeout_s=cfg.request_timeout_s,
    )
    sync = LedFxSceneSync(
        library=library,
        client=client,
        interval_s=cfg.scene_refresh_s,
    )
    return client, sync
