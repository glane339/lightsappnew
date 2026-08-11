"""
Seed the basement rig's DMX devices into the library.

Run from the repository root once, or after adding a fixture to RIG:

    .\\venv\\Scripts\\python.exe backend\\seed_devices.py

Channel tables for each model live in docs/fixtures/.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from models.DMX_Device import DMX_Device
from storage.library import Library
from storage.records import DMX_DEVICES

logger = logging.getLogger(__name__)

# Addresses here must match what is dialled into each fixture, so they are carried
# over from the previous app's positional layout (24-channel blocks per device)
# rather than compacted. Channel counts, by contrast, come from the manuals: the old
# 24 was padding, and an overlong count would leave a phantom channel in every look.
RIG: Tuple[Dict[str, Any], ...] = (
    {
        "name": "GigBAR 2",
        "model": "chauvet_gigbar_2",
        "mode": "23CH",
        "universe": 1,
        "start_address": 1,
        "channel_count": 23,
    },
    {
        "name": "Keobin Light Bar",
        "model": "keobin_light_bar",
        "mode": "18CH",
        "universe": 1,
        "start_address": 25,
        "channel_count": 18,
    },
)


def seed_devices(library: Library) -> List[DMX_Device]:
    """
    Add any device in RIG the library does not already hold, matched by name.

    Devices already present are left untouched, including their addresses — a
    re-patched fixture is the operator's decision, not this script's. Returns only
    the devices that were added, so a fresh seed is distinguishable from a no-op.
    """
    existing = {device.name for device in library.all(DMX_DEVICES)}
    added: List[DMX_Device] = []

    for spec in RIG:
        if spec["name"] in existing:
            continue
        added.append(library.add(DMX_Device(**spec)))

    if added:
        logger.info("seeded %d dmx device(s): %s", len(added), [d.name for d in added])
    return added


def main() -> None:
    from logging_setup import configure_logging

    configure_logging()
    library = Library.open()
    if seed_devices(library):
        library.save()

    for device in sorted(library.all(DMX_DEVICES), key=lambda d: (d.universe, d.start_address)):
        logger.info(
            "universe %d, channels %d-%d: %s (%s)",
            device.universe,
            device.start_address,
            device.end_address,
            device.name,
            device.mode,
        )


if __name__ == "__main__":
    main()
