from __future__ import annotations

import json
from typing import List

import httpx
import pytest

from ledfx.client import LedFxClient, LedFxError, LedFxScene, NullLedFxClient
from ledfx.scene_sync import LedFxSceneSync
from ledfx.service import build_ledfx_stack
from storage.config import LedfxConfig


def test_null_client_records_calls_without_a_socket() -> None:
    client = NullLedFxClient()
    client.set_scenes([LedFxScene(name="Living Room", slug="living-room")])

    listed = client.list_scenes()
    client.activate_scene("Living Room")
    client.close()

    assert [scene.name for scene in listed] == ["Living Room"]
    assert client.calls == [("list_scenes",), ("activate_scene", "Living Room"), ("close",)]
    assert client.reachable is True


def test_client_parses_scenes_and_activates_by_slug() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/scenes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "scenes": {"living-room": {"name": "Living Room"}},
                },
            )
        if request.method == "PUT" and request.url.path == "/api/scenes":
            payload = json.loads(request.read())
            assert payload == {"id": "living-room", "action": "activate"}
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(404, json={"status": "error"})

    http = httpx.Client(
        base_url="http://ledfx.test",
        transport=httpx.MockTransport(handler),
    )
    client = LedFxClient(client=http)
    try:
        scenes = client.list_scenes()
        assert scenes == [LedFxScene(name="Living Room", slug="living-room")]
        assert client.reachable is True
        client.activate_scene("Living Room")
        client.activate_scene("Living Room")  # dedup while reachable
    finally:
        client.close()


def test_client_marks_unreachable_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    http = httpx.Client(
        base_url="http://ledfx.test",
        transport=httpx.MockTransport(handler),
    )
    client = LedFxClient(client=http)
    try:
        with pytest.raises(LedFxError):
            client.list_scenes()
        assert client.reachable is False
    finally:
        client.close()


def test_scene_sync_upserts_missing_names() -> None:
    client = NullLedFxClient()
    client.set_scenes(
        [
            LedFxScene(name="Living Room", slug="living-room"),
            LedFxScene(name="Kitchen", slug="kitchen"),
        ]
    )
    added: List[str] = []

    def upsert(names: List[str]) -> int:
        new = [name for name in names if name not in added]
        added.extend(new)
        return len(new)

    sync = LedFxSceneSync(upsert, client, interval_s=25.0)
    assert sync.refresh_once() == 2
    assert sync.refresh_once() == 0
    assert added == ["Living Room", "Kitchen"]


def test_scene_sync_survives_ledfx_error(caplog: pytest.LogCaptureFixture) -> None:
    class BoomClient(NullLedFxClient):
        def list_scenes(self) -> List[LedFxScene]:
            raise LedFxError("timeout")

    upserts = 0

    def upsert(_names: List[str]) -> int:
        nonlocal upserts
        upserts += 1
        return 0

    sync = LedFxSceneSync(upsert, BoomClient(), interval_s=25.0)
    with caplog.at_level("WARNING"):
        assert sync.refresh_once() == 0
    assert upserts == 0
    assert "skipped" in caplog.text


def test_scene_sync_survives_unexpected_list_and_upsert_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class WeirdClient(NullLedFxClient):
        def list_scenes(self) -> List[LedFxScene]:
            raise RuntimeError("parser exploded")

    sync = LedFxSceneSync(lambda _n: 0, WeirdClient(), interval_s=25.0)
    with caplog.at_level("ERROR"):
        assert sync.refresh_once() == 0
    assert "unexpectedly" in caplog.text

    class OkClient(NullLedFxClient):
        def list_scenes(self) -> List[LedFxScene]:
            return [LedFxScene(name="A", slug="a")]

    def boom(_names: List[str]) -> int:
        raise RuntimeError("save failed")

    sync = LedFxSceneSync(boom, OkClient(), interval_s=25.0)
    caplog.clear()
    with caplog.at_level("ERROR"):
        assert sync.refresh_once() == 0
    assert "upsert failed" in caplog.text


def test_build_ledfx_stack_disabled_is_null() -> None:
    client, sync = build_ledfx_stack(LedfxConfig(enabled=False), lambda _n: 0)
    assert isinstance(client, NullLedFxClient)
    assert sync is None


def test_scene_sync_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        LedFxSceneSync(lambda _n: 0, NullLedFxClient(), interval_s=0)
