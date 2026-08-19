from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, List, Optional

import pytest
from conftest import build_cycling_scene_graph
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.app import create_app
from server.commands import CommandKind, ShowCommand
from server.engine import ShowEngine
from server.routes.diag import SelfTestRequest, selftest
from storage.config import AppConfig
from storage.library import Library

WAIT_S = 3.0


class RecordingTransport:
    """Keeps every frame, and remembers how many had arrived when it was closed."""

    def __init__(self) -> None:
        self.frames: List[List[int]] = []
        self.closed_after: Optional[int] = None

    @property
    def name(self) -> str:
        return "recording"

    def send(self, channels: List[int]) -> None:
        self.frames.append(list(channels))

    def close(self) -> None:
        self.closed_after = len(self.frames)


def _seed_scene(data_root: Path) -> str:
    """Write a playable scene to disk, so the app's own Library loads it on open."""
    library = Library.open(data_root, sync_ilda=False)
    graph = build_cycling_scene_graph(library, dmx_beats=2, wled_beats=3)
    library.save()
    return graph.scene_id


def _client(data_root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(), data_root=data_root))


def _wait_until(predicate: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _wait_for_active(client: TestClient, scene_id: Optional[str]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if client.get("/api/show/state").json()["active_scene_id"] == scene_id:
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def client(data_root: Path):
    with _client(data_root) as test_client:
        yield test_client


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shutdown_is_a_noop_without_a_callback(client: TestClient) -> None:
    response = client.post("/api/shutdown")

    assert response.status_code == 200
    assert response.json() == {"status": "stopping"}
    assert client.get("/api/health").json() == {"status": "ok"}


def test_shutdown_invokes_the_server_callback(data_root: Path) -> None:
    app = create_app(AppConfig(), data_root=data_root)
    called: List[bool] = []
    app.state.request_shutdown = lambda: called.append(True)

    with TestClient(app) as client:
        response = client.post("/api/shutdown")

    assert response.status_code == 200
    assert response.json() == {"status": "stopping"}
    assert called == [True]


def test_scene_list_is_empty_without_a_library(client: TestClient) -> None:
    assert client.get("/api/scenes").json() == {"scenes": []}


def test_scene_list_reports_stored_scenes(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client:
        scenes = client.get("/api/scenes").json()["scenes"]

    assert [scene["id"] for scene in scenes] == [scene_id]
    assert scenes[0]["sensitivity"] == 0.5


def test_activating_over_rest_lights_the_rig(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client:
        response = client.post("/api/show/activate", json={"id": scene_id})
        assert response.status_code == 200
        assert response.json()["accepted"] is True

        assert _wait_for_active(client, scene_id), "scene never became active"

        status = client.get("/api/status").json()
        assert status["is_active"] is True
        assert status["sender"]["transport"] == "null"
        assert status["sender"]["frames_sent"] >= 1
        # A frame reaching the transport is what the ledger times.
        assert status["latency"]["count"] >= 1


def test_deactivate_stops_the_show(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client:
        client.post("/api/show/activate", json={"id": scene_id})
        assert _wait_for_active(client, scene_id)

        client.post("/api/show/deactivate")

        assert _wait_for_active(client, None)
        assert client.get("/api/show/state").json()["is_active"] is False


def test_blackout_zeroes_the_universe_and_stops_sequencing(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client:
        client.post("/api/show/activate", json={"id": scene_id})
        assert _wait_for_active(client, scene_id)

        client.post("/api/show/blackout")
        assert _wait_for_active(client, None)

        engine = client.app.state.engine
        assert engine.transport.last_channels is not None
        assert set(engine.transport.last_channels) == {0}


def test_activate_requires_a_scene_id(client: TestClient) -> None:
    assert client.post("/api/show/activate", json={"id": ""}).status_code == 422


def test_websocket_pushes_state_and_a_timed_ack(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client, client.websocket_connect("/ws/show") as socket:
        socket.send_json({"t": "activate", "id": scene_id, "ack": "probe-1"})

        seen = _await_kinds(socket, {"state", "ack"})

        assert seen["state"]["active_scene_id"] == scene_id
        assert seen["ack"]["id"] == "probe-1"
        # The whole point of the exercise: the round trip is inside the budget.
        from server.latency import LATENCY_BUDGET_US

        assert 0 <= seen["ack"]["latency_us"] <= LATENCY_BUDGET_US


def test_websocket_reports_an_unknown_scene_as_an_error(client: TestClient) -> None:
    with client.websocket_connect("/ws/show") as socket:
        socket.send_json({"t": "activate", "id": "no-such-scene"})

        error = _await_kinds(socket, {"error"})["error"]

        assert "no-such-scene" in error["message"]


def test_websocket_rejects_malformed_frames(client: TestClient) -> None:
    with client.websocket_connect("/ws/show") as socket:
        socket.send_text("{not json")
        assert socket.receive_json()["t"] == "error"

        socket.send_json({"t": "fly-to-the-moon"})
        assert "unknown message type" in socket.receive_json()["message"]


def test_websocket_pushes_a_beat_event(client: TestClient) -> None:
    with client.websocket_connect("/ws/show") as socket:
        socket.send_json({"t": "beat"})
        seen = _await_kinds(socket, {"beat", "state", "ack"})
        assert seen["beat"] == {"t": "beat"}


def test_beat_advances_the_active_scene(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client, client.websocket_connect("/ws/show") as socket:
        socket.send_json({"t": "activate", "id": scene_id})
        _await_kinds(socket, {"state", "ack"})
        engine = client.app.state.engine
        first_look = list(engine.transport.last_channels or [])

        # The cue list advances every two beats, so two taps change the look.
        socket.send_json({"t": "beat"})
        socket.send_json({"t": "beat"})
        _await_count(socket, "ack", 2)

        assert engine.transport.last_channels != first_look


def test_selftest_reports_percentiles_within_budget(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)

    with _client(data_root) as client:
        response = client.post(
            "/api/diag/selftest",
            json={"scene_id": scene_id, "count": 50, "gap_ms": 1.0},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["measured"] == 50
    assert body["latency"]["p99_us"] > 0
    assert body["within_budget"] is True, f"p99 was {body['latency']['p99_us']} µs"


def test_selftest_refuses_to_run_against_a_live_transport() -> None:
    class LiveTransportEngine:
        def sender_health(self) -> dict:
            return {"transport": "e131"}

    with pytest.raises(HTTPException) as raised:
        selftest(SelfTestRequest(scene_id="any-scene"), LiveTransportEngine())

    assert raised.value.status_code == 409
    assert "e131" in raised.value.detail


def test_shutdown_blacks_out_before_closing_the_transport(data_root: Path) -> None:
    scene_id = _seed_scene(data_root)
    transport = RecordingTransport()
    engine = ShowEngine(
        Library.open(data_root, sync_ilda=False), AppConfig(), transport=transport
    )

    engine.start()
    try:
        engine.submit(
            ShowCommand(
                kind=CommandKind.ACTIVATE,
                received_ns=time.perf_counter_ns(),
                scene_id=scene_id,
            )
        )
        assert _wait_until(lambda: any(set(frame) != {0} for frame in transport.frames))
    finally:
        engine.stop()

    assert set(transport.frames[-1]) == {0}, "the rig was left lit at shutdown"
    assert transport.closed_after == len(transport.frames), "closed before the blackout"


def test_operator_page_is_served_at_the_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Lights" in response.text
    assert "Performance" in response.text
    assert "Builder" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/performance/",
        "/builder/gigbar2/",
        "/builder/keobin/",
        "/builder/dmx-presets/",
        "/builder/dmx-preset-lists/",
        "/builder/wled-preset-lists/",
        "/builder/scenes/",
        "/diag/",
        "/about/",
        "/css/app.css",
        "/js/api.js",
        "/js/show.js",
        "/js/fixtures/chauvet_gigbar_2.js",
        "/js/fixtures/keobin_light_bar.js",
    ],
)
def test_ws11_static_pages_are_served(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200, path


def _await_kinds(socket, kinds: set) -> dict:
    """
    Read frames until one of every requested kind has arrived, keyed by kind.

    State and ack race each other — the ack is produced on the sender thread, the state
    on the show thread — so tests match on kind rather than assuming an order.
    """
    seen: dict = {}
    for _ in range(len(kinds) + 6):
        message = socket.receive_json()
        seen.setdefault(message["t"], message)
        if kinds <= set(seen):
            return seen
    raise AssertionError(f"saw {sorted(seen)} while waiting for {sorted(kinds)}")


def _await_count(socket, kind: str, count: int) -> list:
    collected: list = []
    for _ in range(count + 6):
        message = socket.receive_json()
        if message["t"] == kind:
            collected.append(message)
        if len(collected) >= count:
            return collected
    raise AssertionError(f"only saw {len(collected)} {kind} frames, wanted {count}")
