from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

import httpx

from config.config import LEDFX_BASE_URL

logger = logging.getLogger(__name__)


class LedFxError(Exception):
    """LEDfx HTTP or protocol failure."""


@dataclass(frozen=True)
class LedFxScene:
    """One scene as returned by LEDfx. ``name`` is stored; ``slug`` is used to activate."""

    name: str
    slug: str


class LedFxClientProtocol(Protocol):
    @property
    def reachable(self) -> bool: ...

    def list_scenes(self) -> List[LedFxScene]: ...

    def activate_scene(self, name: str) -> None: ...

    def deactivate_scene(self, name: str) -> None: ...

    def slug_for(self, name: str) -> Optional[str]: ...

    def close(self) -> None: ...


class LedFxClient:
    """
    HTTP adapter for LEDfx. The only module that talks to the LEDfx REST API.

    Does not read or write the Library. Scene names are resolved to LEDfx slugs via
    the in-memory map filled by list_scenes().
    """

    def __init__(
        self,
        base_url: str = LEDFX_BASE_URL,
        timeout_s: float = 2.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._owns_client = client is None
        self._http = client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout_s,
        )
        self._name_to_slug: Dict[str, str] = {}
        self._active_name: Optional[str] = None
        self._reachable = False
        self._logged_unreachable = False

    @property
    def reachable(self) -> bool:
        return self._reachable

    def slug_for(self, name: str) -> Optional[str]:
        return self._name_to_slug.get(name)

    def list_scenes(self) -> List[LedFxScene]:
        try:
            response = self._http.get("/api/scenes")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._mark_unreachable(exc)
            raise LedFxError(f"failed to list LEDfx scenes: {exc}") from exc

        if payload.get("status") != "success":
            reason = _payload_reason(payload) or "unknown error"
            self._mark_unreachable(reason)
            raise LedFxError(f"LEDfx list scenes failed: {reason}")

        scenes_obj = payload.get("scenes") or {}
        if not isinstance(scenes_obj, dict):
            raise LedFxError("LEDfx list scenes response missing scenes object")

        scenes: List[LedFxScene] = []
        name_to_slug: Dict[str, str] = {}
        for slug, config in scenes_obj.items():
            if not isinstance(config, dict):
                continue
            name = config.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            scenes.append(LedFxScene(name=name, slug=str(slug)))
            name_to_slug[name] = str(slug)

        self._name_to_slug = name_to_slug
        self._mark_reachable()
        return scenes

    def activate_scene(self, name: str) -> None:
        if name == self._active_name and self._reachable:
            return
        slug = self._resolve_slug(name)
        self._mutate_scene(slug, "activate")
        self._active_name = name

    def deactivate_scene(self, name: str) -> None:
        slug = self._resolve_slug(name)
        self._mutate_scene(slug, "deactivate")
        if self._active_name == name:
            self._active_name = None

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def _resolve_slug(self, name: str) -> str:
        slug = self._name_to_slug.get(name)
        if slug is not None:
            return slug
        self.list_scenes()
        slug = self._name_to_slug.get(name)
        if slug is None:
            raise LedFxError(f"unknown LEDfx scene name {name!r}")
        return slug

    def _mutate_scene(self, slug: str, action: str) -> None:
        body = {"id": slug, "action": action}
        try:
            response = self._http.put("/api/scenes", json=body)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._mark_unreachable(exc)
            raise LedFxError(f"failed to {action} LEDfx scene {slug!r}: {exc}") from exc

        if payload.get("status") != "success":
            reason = _payload_reason(payload) or "unknown error"
            # Bad scene id is not a connectivity failure — keep prior reachability.
            raise LedFxError(f"LEDfx {action} failed for {slug!r}: {reason}")

        self._mark_reachable()

    def _mark_reachable(self) -> None:
        self._reachable = True
        self._logged_unreachable = False

    def _mark_unreachable(self, detail: object) -> None:
        was_reachable = self._reachable
        self._reachable = False
        self._active_name = None  # invalidate dedup after disconnect / restart
        if was_reachable or not self._logged_unreachable:
            logger.warning("LEDfx unreachable: %s", detail)
            self._logged_unreachable = True


class NullLedFxClient:
    """Default no-op client. Records calls for tests; never opens a socket."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self._name_to_slug: Dict[str, str] = {}
        self._scenes: List[LedFxScene] = []
        self._reachable = True

    @property
    def reachable(self) -> bool:
        return self._reachable

    def set_scenes(self, scenes: List[LedFxScene]) -> None:
        self._scenes = list(scenes)
        self._name_to_slug = {scene.name: scene.slug for scene in scenes}

    def slug_for(self, name: str) -> Optional[str]:
        return self._name_to_slug.get(name)

    def list_scenes(self) -> List[LedFxScene]:
        self.calls.append(("list_scenes",))
        return list(self._scenes)

    def activate_scene(self, name: str) -> None:
        self.calls.append(("activate_scene", name))

    def deactivate_scene(self, name: str) -> None:
        self.calls.append(("deactivate_scene", name))

    def close(self) -> None:
        self.calls.append(("close",))


def _payload_reason(payload: dict) -> Optional[str]:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        reason = nested.get("reason")
        if isinstance(reason, str):
            return reason
    return None
