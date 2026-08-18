from __future__ import annotations

from typing import Callable, Optional, Sequence, Tuple

from ledfx.client import LedFxClient, LedFxClientProtocol, NullLedFxClient
from ledfx.scene_sync import LedFxSceneSync
from storage.config import LedfxConfig


def build_ledfx_stack(
    config: LedfxConfig,
    upsert: Callable[[Sequence[str]], int],
) -> Tuple[LedFxClientProtocol, Optional[LedFxSceneSync]]:
    """
    Construct the LEDfx client and optional scene sync from config.

    ``upsert`` is the authoring service's ``upsert_wled_presets`` — the sync thread's
    only path into storage. When ``enabled`` is false, returns a ``NullLedFxClient``
    and no sync loop.
    """
    if not config.enabled:
        return NullLedFxClient(), None

    client = LedFxClient(
        base_url=config.base_url,
        timeout_s=config.request_timeout_s,
    )
    sync = LedFxSceneSync(
        upsert=upsert,
        client=client,
        interval_s=config.scene_refresh_s,
    )
    return client, sync
