from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from models.DMX_Device import DMX_Device
from server.app import create_app
from storage.config import AppConfig
from storage.library import Library

WAIT_S = 3.0


def _client(data_root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(), data_root=data_root))


def _seed_device(data_root: Path) -> str:
    library = Library.open(data_root, sync_ilda=False)
    device = DMX_Device(name="Test Par", start_address=1, channel_count=3)
    library.add(device)
    library.save()
    return device.id


def _wait_for_active(client: TestClient, scene_id: Optional[str]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if client.get("/api/show/state").json()["active_scene_id"] == scene_id:
            return True
        time.sleep(0.005)
    return False


def _wait_for_channels(engine, expected: list) -> bool:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        channels = engine.transport.last_channels
        if channels is not None and list(channels[: len(expected)]) == expected:
            return True
        time.sleep(0.005)
    return False


def _error(response) -> dict:
    return response.json()["error"]


def _create_playable_scene(client: TestClient, device_id: str, scene_id: str = "red-wash") -> dict:
    device_preset = client.post(
        "/api/dmx-device-presets",
        json={"device_id": device_id, "channel_values": [10, 20, 30]},
    )
    assert device_preset.status_code == 201, device_preset.text

    look = client.post(
        "/api/dmx-presets",
        json={"dmx_device_preset_ids": [device_preset.json()["id"]]},
    )
    assert look.status_code == 201, look.text

    dmx_list = client.post(
        "/api/dmx-preset-lists",
        json={"dmx_preset_ids": [look.json()["id"]], "beats": 2},
    )
    assert dmx_list.status_code == 201, dmx_list.text

    wled = client.post("/api/wled-presets", json={"name": "scene-alpha"})
    assert wled.status_code == 201, wled.text

    wled_list = client.post(
        "/api/wled-preset-lists",
        json={"wled_preset_ids": ["scene-alpha"], "beats": 4},
    )
    assert wled_list.status_code == 201, wled_list.text

    preset = client.post(
        "/api/presets",
        json={
            "id": "wash-pair",
            "dmx_preset_list_id": dmx_list.json()["id"],
            "wled_preset_list_id": wled_list.json()["id"],
        },
    )
    assert preset.status_code == 201, preset.text

    scene = client.post(
        "/api/scenes",
        json={"id": scene_id, "preset_id": preset.json()["id"]},
    )
    assert scene.status_code == 201, scene.text
    return scene.json()


def test_http_create_graph_then_activate(data_root: Path) -> None:
    device_id = _seed_device(data_root)

    with _client(data_root) as client:
        devices = client.get("/api/dmx-devices").json()["dmx_devices"]
        assert devices[0]["id"] == device_id
        assert devices[0]["end_address"] == 3

        scene = _create_playable_scene(client, device_id)
        assert scene["id"] == "red-wash"
        assert "sensitivity" not in scene

        listed = client.get("/api/scenes").json()["scenes"]
        assert listed[0]["id"] == "red-wash"

        fetched = client.get("/api/scenes/red-wash")
        assert fetched.status_code == 200
        assert fetched.json()["preset_id"] == scene["preset_id"]

        response = client.post("/api/show/activate", json={"id": "red-wash"})
        assert response.status_code == 200
        assert _wait_for_active(client, "red-wash"), "authored scene never became active"


def test_http_posted_looks_update_universe_when_the_beat_cycles(data_root: Path) -> None:
    device_id = _seed_device(data_root)

    with _client(data_root) as client:
        red = client.post(
            "/api/dmx-device-presets",
            json={"id": "par-red", "device_id": device_id, "channel_values": [255, 0, 0]},
        )
        blue = client.post(
            "/api/dmx-device-presets",
            json={"id": "par-blue", "device_id": device_id, "channel_values": [0, 0, 255]},
        )
        assert red.status_code == 201, red.text
        assert blue.status_code == 201, blue.text

        look_red = client.post(
            "/api/dmx-presets", json={"id": "all-red", "dmx_device_preset_ids": ["par-red"]}
        )
        look_blue = client.post(
            "/api/dmx-presets", json={"id": "all-blue", "dmx_device_preset_ids": ["par-blue"]}
        )
        assert look_red.status_code == 201, look_red.text
        assert look_blue.status_code == 201, look_blue.text

        dmx_list = client.post(
            "/api/dmx-preset-lists",
            json={"id": "wash-cycle", "dmx_preset_ids": ["all-red", "all-blue"], "beats": 1},
        )
        wled = client.post("/api/wled-presets", json={"name": "scene-alpha"})
        wled_list = client.post(
            "/api/wled-preset-lists",
            json={"wled_preset_ids": ["scene-alpha"], "beats": 8},
        )
        assert dmx_list.status_code == 201, dmx_list.text
        assert wled.status_code == 201, wled.text
        assert wled_list.status_code == 201, wled_list.text

        preset = client.post(
            "/api/presets",
            json={
                "dmx_preset_list_id": "wash-cycle",
                "wled_preset_list_id": wled_list.json()["id"],
            },
        )
        scene = client.post(
            "/api/scenes",
            json={"id": "cycle", "preset_id": preset.json()["id"]},
        )
        assert preset.status_code == 201, preset.text
        assert scene.status_code == 201, scene.text

        engine = client.app.state.engine
        client.post("/api/show/activate", json={"id": "cycle"})
        assert _wait_for_active(client, "cycle")
        assert _wait_for_channels(engine, [255, 0, 0]), engine.transport.last_channels

        client.post("/api/show/beat")
        assert _wait_for_channels(engine, [0, 0, 255]), engine.transport.last_channels

        client.post("/api/show/beat")
        assert _wait_for_channels(engine, [255, 0, 0]), engine.transport.last_channels


def test_http_not_found_is_404(data_root: Path) -> None:
    with _client(data_root) as client:
        response = client.get("/api/scenes/missing")
        assert response.status_code == 404
        assert _error(response) == {
            "code": "not_found",
            "message": "no scenes with id 'missing'",
        }


def test_http_invalid_scene_is_400(data_root: Path) -> None:
    with _client(data_root) as client:
        response = client.post("/api/scenes", json={"preset_id": "nope"})
        assert response.status_code == 400
        body = _error(response)
        assert body["code"] == "invalid"
        assert "nope" in body["message"]


def test_http_duplicate_wled_name_is_409(data_root: Path) -> None:
    with _client(data_root) as client:
        first = client.post("/api/wled-presets", json={"name": "Living Room"})
        assert first.status_code == 201
        again = client.post("/api/wled-presets", json={"name": "Living Room"})
        assert again.status_code == 409
        assert _error(again)["code"] == "conflict"


def test_http_delete_refuses_without_force(data_root: Path) -> None:
    device_id = _seed_device(data_root)
    with _client(data_root) as client:
        scene = _create_playable_scene(client, device_id)
        preset_id = scene["preset_id"]

        plan = client.get(f"/api/presets/{preset_id}/delete-plan")
        assert plan.status_code == 200
        removed_ids = {item["id"] for item in plan.json()["removes"]}
        assert preset_id in removed_ids
        assert "red-wash" in removed_ids

        refused = client.delete(f"/api/presets/{preset_id}")
        assert refused.status_code == 409
        assert _error(refused)["code"] == "conflict"

        forced = client.delete(f"/api/presets/{preset_id}?force=true")
        assert forced.status_code == 200
        assert client.get("/api/scenes/red-wash").status_code == 404


def test_http_device_preset_look_and_list_stack(data_root: Path) -> None:
    device_id = _seed_device(data_root)

    with _client(data_root) as client:
        red = client.post(
            "/api/dmx-device-presets",
            json={
                "id": "par-red",
                "device_id": device_id,
                "channel_values": [255, 0, 0],
            },
        )
        assert red.status_code == 201, red.text
        assert red.json() == {
            "id": "par-red",
            "device_id": device_id,
            "channel_values": [255, 0, 0],
        }

        blue = client.post(
            "/api/dmx-device-presets",
            json={"id": "par-blue", "device_id": device_id, "channel_values": [0, 0, 255]},
        )
        assert blue.status_code == 201, blue.text

        look_red = client.post(
            "/api/dmx-presets",
            json={"id": "all-red", "dmx_device_preset_ids": ["par-red"]},
        )
        look_blue = client.post(
            "/api/dmx-presets",
            json={"id": "all-blue", "dmx_device_preset_ids": ["par-blue"]},
        )
        assert look_red.status_code == 201, look_red.text
        assert look_blue.status_code == 201, look_blue.text
        assert look_red.json()["dmx_device_preset_ids"] == ["par-red"]

        listed_rows = client.get("/api/dmx-device-presets")
        assert listed_rows.status_code == 200
        assert {row["id"] for row in listed_rows.json()["dmx_device_presets"]} == {
            "par-red",
            "par-blue",
        }

        cue_list = client.post(
            "/api/dmx-preset-lists",
            json={
                "id": "wash-cycle",
                "dmx_preset_ids": ["all-red", "all-blue", "all-red"],
                "beats": 4,
            },
        )
        assert cue_list.status_code == 201, cue_list.text
        assert cue_list.json() == {
            "id": "wash-cycle",
            "dmx_preset_ids": ["all-red", "all-blue", "all-red"],
            "beats": 4,
        }

        fetched = client.get("/api/dmx-preset-lists/wash-cycle")
        assert fetched.status_code == 200
        assert fetched.json()["dmx_preset_ids"] == ["all-red", "all-blue", "all-red"]

        updated = client.put(
            "/api/dmx-device-presets/par-red",
            json={"channel_values": [200, 10, 10]},
        )
        assert updated.status_code == 200
        assert updated.json()["channel_values"] == [200, 10, 10]

        wled = client.post("/api/wled-presets", json={"name": "Living Room"})
        assert wled.status_code == 201, wled.text
        wled_list = client.post(
            "/api/wled-preset-lists",
            json={"id": "strip-cycle", "wled_preset_ids": ["Living Room"], "beats": 2},
        )
        assert wled_list.status_code == 201, wled_list.text

        preset = client.post(
            "/api/presets",
            json={
                "id": "red-wash-stripes",
                "dmx_preset_list_id": "wash-cycle",
                "wled_preset_list_id": "strip-cycle",
            },
        )
        assert preset.status_code == 201, preset.text
        assert preset.json()["dmx_preset_list_id"] == "wash-cycle"
        assert preset.json()["wled_preset_list_id"] == "strip-cycle"

        scene = client.post(
            "/api/scenes",
            json={"id": "red-wash", "preset_id": "red-wash-stripes"},
        )
        assert scene.status_code == 201, scene.text
        assert scene.json()["preset_id"] == "red-wash-stripes"


def test_http_device_preset_rejects_wrong_channel_count(data_root: Path) -> None:
    device_id = _seed_device(data_root)
    with _client(data_root) as client:
        response = client.post(
            "/api/dmx-device-presets",
            json={"device_id": device_id, "channel_values": [1, 2]},
        )
        assert response.status_code == 400
        body = _error(response)
        assert body["code"] == "invalid"
        assert "exactly 3" in body["message"]


def test_http_create_scene_from_cue_lists(data_root: Path) -> None:
    device_id = _seed_device(data_root)
    with _client(data_root) as client:
        device_preset = client.post(
            "/api/dmx-device-presets",
            json={"device_id": device_id, "channel_values": [10, 20, 30]},
        )
        look = client.post(
            "/api/dmx-presets",
            json={"dmx_device_preset_ids": [device_preset.json()["id"]]},
        )
        dmx_list = client.post(
            "/api/dmx-preset-lists",
            json={"dmx_preset_ids": [look.json()["id"]], "beats": 1},
        )
        client.post("/api/wled-presets", json={"name": "Living Room"})
        wled_list = client.post(
            "/api/wled-preset-lists",
            json={"wled_preset_ids": ["Living Room"], "beats": 1},
        )

        scene = client.post(
            "/api/scenes",
            json={
                "id": "paired",
                "dmx_preset_list_id": dmx_list.json()["id"],
                "wled_preset_list_id": wled_list.json()["id"],
            },
        )
        assert scene.status_code == 201, scene.text
        assert scene.json()["id"] == "paired"
        assert scene.json()["preset_id"]

        again = client.post(
            "/api/scenes",
            json={
                "id": "paired-2",
                "dmx_preset_list_id": dmx_list.json()["id"],
                "wled_preset_list_id": wled_list.json()["id"],
            },
        )
        assert again.status_code == 201, again.text
        assert again.json()["preset_id"] == scene.json()["preset_id"]


def test_ledfx_refresh_conflicts_when_disabled(data_root: Path) -> None:
    with _client(data_root) as client:
        response = client.post("/api/ledfx/refresh")
        assert response.status_code == 409

