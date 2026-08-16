"""
E1.31 (sACN) packet framing.

Hand-rolled rather than taken from a library (D-020): the layout is fixed, the only
things that move between frames are the sequence number and the 512 slots, and owning
the bytes keeps the send-on-change wake path free of a third party's threading model.

Nothing here opens a socket. This module turns a channel list into bytes, which is what
makes it testable by asserting on those bytes instead of on the network.
"""

from __future__ import annotations

import struct
import uuid
from typing import Dict, Sequence

from models.Active_DMX_Channels import UNIVERSE_SIZE

SACN_PORT = 5568

# ACN identifiers, fixed by E1.31 §4.1.
ACN_PACKET_IDENTIFIER = b"ASC-E1.17\x00\x00\x00"
PREAMBLE_SIZE = 0x0010
POSTAMBLE_SIZE = 0x0000

VECTOR_ROOT_E131_DATA = 0x00000004
VECTOR_E131_DATA_PACKET = 0x00000002
VECTOR_DMP_SET_PROPERTY = 0x02

# DMP addressing for a contiguous, single-octet property block.
ADDRESS_AND_DATA_TYPE = 0xA1
FIRST_PROPERTY_ADDRESS = 0x0000
ADDRESS_INCREMENT = 0x0001
DMX_START_CODE = 0x00

# Every PDU in a DATA packet carries the same flags in the top nibble of its length word.
PDU_FLAGS = 0x7000

# Options bits (E1.31 §6.2.6). Preview_Data is unused: this app never sends preview data.
OPTION_PREVIEW_DATA = 0x80
OPTION_STREAM_TERMINATED = 0x40

SOURCE_NAME_SIZE = 64
CID_SIZE = 16

MIN_UNIVERSE = 1
MAX_UNIVERSE = 63999
MAX_PRIORITY = 200
SEQUENCE_MODULUS = 256

# The three PDUs, in bytes, for a full 512-slot frame.
ROOT_LAYER_SIZE = 38
FRAMING_LAYER_SIZE = 77
DMP_LAYER_SIZE = 11 + UNIVERSE_SIZE
PACKET_SIZE = ROOT_LAYER_SIZE + FRAMING_LAYER_SIZE + DMP_LAYER_SIZE

# Preamble, post-amble, and the ACN identifier sit outside the root PDU's own length.
_ROOT_LENGTH_OFFSET = 16

_ROOT_FLAGS_LENGTH = PDU_FLAGS | (PACKET_SIZE - _ROOT_LENGTH_OFFSET)
_FRAMING_FLAGS_LENGTH = PDU_FLAGS | (PACKET_SIZE - ROOT_LAYER_SIZE)
_DMP_FLAGS_LENGTH = PDU_FLAGS | DMP_LAYER_SIZE

# Slots plus the start code, which the protocol counts as a property value.
_PROPERTY_VALUE_COUNT = UNIVERSE_SIZE + 1

# A CID must be stable for the lifetime of a source, or receivers treat every restart as
# a new sender. Deriving it from the source name gets that for free and keeps the value
# reproducible in tests, where a random UUID would not be.
_CID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "lightsapp.e131")

DEFAULT_SOURCE_NAME = "Lights App"


def cid_from_source_name(source_name: str) -> bytes:
    """The 16-byte CID this source identifies itself with, stable across restarts."""
    return uuid.uuid5(_CID_NAMESPACE, source_name).bytes


def multicast_host(universe: int) -> str:
    """The 239.255.x.y group a receiver joins for one universe (E1.31 Appendix A)."""
    _check_universe(universe)
    return f"239.255.{(universe >> 8) & 0xFF}.{universe & 0xFF}"


def build_data_packet(
    *,
    cid: bytes,
    source_name: str,
    universe: int,
    priority: int,
    sequence: int,
    channels: Sequence[int],
    options: int = 0,
    sync_address: int = 0,
) -> bytes:
    """
    Frame one universe as an E1.31 DATA packet.

    Short channel lists are zero-padded and long ones truncated rather than rejected: a
    frame that is the wrong length is a programming error upstream, and going dark
    mid-show over it would be a worse failure than lighting the slots that are correct.
    """
    if len(cid) != CID_SIZE:
        raise ValueError(f"cid must be {CID_SIZE} bytes, got {len(cid)}")
    _check_universe(universe)
    if not 0 <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be 0..{MAX_PRIORITY}, got {priority}")
    if not 0 <= sequence < SEQUENCE_MODULUS:
        raise ValueError(f"sequence must be 0..{SEQUENCE_MODULUS - 1}, got {sequence}")

    root = struct.pack(
        "!HH12sHI16s",
        PREAMBLE_SIZE,
        POSTAMBLE_SIZE,
        ACN_PACKET_IDENTIFIER,
        _ROOT_FLAGS_LENGTH,
        VECTOR_ROOT_E131_DATA,
        cid,
    )
    framing = struct.pack(
        "!HI64sBHBBH",
        _FRAMING_FLAGS_LENGTH,
        VECTOR_E131_DATA_PACKET,
        _encode_source_name(source_name),
        priority,
        sync_address,
        sequence,
        options,
        universe,
    )
    dmp = struct.pack(
        "!HBBHHHB",
        _DMP_FLAGS_LENGTH,
        VECTOR_DMP_SET_PROPERTY,
        ADDRESS_AND_DATA_TYPE,
        FIRST_PROPERTY_ADDRESS,
        ADDRESS_INCREMENT,
        _PROPERTY_VALUE_COUNT,
        DMX_START_CODE,
    )

    return root + framing + dmp + _encode_slots(channels)


class SequenceCounter:
    """
    Per-universe sequence numbers, wrapping 255 back to 0.

    Per universe rather than per sender because a receiver detects reordering by
    comparing against the last number it saw *on that universe*; one shared counter
    would look like permanent packet loss on a multi-universe rig.
    """

    def __init__(self) -> None:
        self._next: Dict[int, int] = {}

    def next(self, universe: int) -> int:
        current = self._next.get(universe, 0)
        self._next[universe] = (current + 1) % SEQUENCE_MODULUS
        return current


def _check_universe(universe: int) -> None:
    if not MIN_UNIVERSE <= universe <= MAX_UNIVERSE:
        raise ValueError(f"universe must be {MIN_UNIVERSE}..{MAX_UNIVERSE}, got {universe}")


def _encode_source_name(source_name: str) -> bytes:
    return source_name.encode("utf-8")[: SOURCE_NAME_SIZE - 1].ljust(SOURCE_NAME_SIZE, b"\x00")


def _encode_slots(channels: Sequence[int]) -> bytes:
    slots = bytearray(UNIVERSE_SIZE)
    for index, value in enumerate(channels[:UNIVERSE_SIZE]):
        slots[index] = 0 if value < 0 else 255 if value > 255 else value
    return bytes(slots)
