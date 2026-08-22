from __future__ import annotations

import struct
from typing import List, Optional, Tuple

import pytest

from models.Active_DMX_Channels import UNIVERSE_SIZE
from runtime.e131 import (
    ACN_PACKET_IDENTIFIER,
    DMP_LAYER_SIZE,
    FRAMING_LAYER_SIZE,
    OPTION_STREAM_TERMINATED,
    PACKET_SIZE,
    ROOT_LAYER_SIZE,
    VECTOR_DMP_SET_PROPERTY,
    VECTOR_E131_DATA_PACKET,
    VECTOR_ROOT_E131_DATA,
    SequenceCounter,
    build_data_packet,
    cid_from_source_name,
    multicast_host,
)
from runtime.sender import E131Transport, NullTransport, build_transport
from storage.config import DMXConfig

SOURCE_NAME = "Lights App"
CID = cid_from_source_name(SOURCE_NAME)

# Offsets into the frame, so a test names the field it asserts on rather than a number.
_FRAMING_START = ROOT_LAYER_SIZE
_SOURCE_NAME_AT = _FRAMING_START + 6
_PRIORITY_AT = _SOURCE_NAME_AT + 64
_SEQUENCE_AT = _PRIORITY_AT + 3
_OPTIONS_AT = _SEQUENCE_AT + 1
_UNIVERSE_AT = _OPTIONS_AT + 1
_DMP_START = ROOT_LAYER_SIZE + FRAMING_LAYER_SIZE
_START_CODE_AT = _DMP_START + 10
_SLOTS_AT = _START_CODE_AT + 1


class FakeSocket:
    """Stands in for a UDP socket, recording everything instead of sending it."""

    def __init__(self, *, fail_on_send: bool = False, fail_on_bind: bool = False) -> None:
        self.sent: List[Tuple[bytes, Tuple[str, int]]] = []
        self.options: List[Tuple[int, int, object]] = []
        self.bound_to: Optional[Tuple[str, int]] = None
        self.closed = False
        self._fail_on_send = fail_on_send
        self._fail_on_bind = fail_on_bind

    def bind(self, address: Tuple[str, int]) -> None:
        if self._fail_on_bind:
            raise OSError("cannot bind")
        self.bound_to = address

    def setsockopt(self, level: int, option: int, value: object) -> None:
        self.options.append((level, option, value))

    def sendto(self, packet: bytes, destination: Tuple[str, int]) -> None:
        if self._fail_on_send:
            raise OSError("network is unreachable")
        self.sent.append((packet, destination))

    def close(self) -> None:
        self.closed = True

    @property
    def packets(self) -> List[bytes]:
        return [packet for packet, _ in self.sent]


def _packet(**overrides) -> bytes:
    fields = {
        "cid": CID,
        "source_name": SOURCE_NAME,
        "universe": 1,
        "priority": 100,
        "sequence": 0,
        "channels": [0] * UNIVERSE_SIZE,
    }
    fields.update(overrides)
    return build_data_packet(**fields)


def _transport(**overrides) -> Tuple[E131Transport, FakeSocket]:
    sock = overrides.pop("sock", None) or FakeSocket()
    settings = {
        "universe": 1,
        "host": "192.168.0.50",
        "port": 5568,
        "priority": 100,
        "source_name": SOURCE_NAME,
    }
    settings.update(overrides)
    return E131Transport(socket_factory=lambda: sock, **settings), sock


def test_layer_sizes_add_up_to_a_full_frame() -> None:
    assert ROOT_LAYER_SIZE + FRAMING_LAYER_SIZE + DMP_LAYER_SIZE == PACKET_SIZE
    assert PACKET_SIZE == 638
    assert len(_packet()) == PACKET_SIZE


def test_root_layer_carries_the_acn_preamble_and_cid() -> None:
    packet = _packet()

    preamble, postamble = struct.unpack("!HH", packet[0:4])
    assert preamble == 0x0010
    assert postamble == 0x0000
    assert packet[4:16] == ACN_PACKET_IDENTIFIER
    assert struct.unpack("!I", packet[18:22])[0] == VECTOR_ROOT_E131_DATA
    assert packet[22:38] == CID


def test_pdu_lengths_count_from_each_layer_to_the_end_of_the_packet() -> None:
    packet = _packet()

    root_flags_length = struct.unpack("!H", packet[16:18])[0]
    framing_flags_length = struct.unpack("!H", packet[_FRAMING_START : _FRAMING_START + 2])[0]
    dmp_flags_length = struct.unpack("!H", packet[_DMP_START : _DMP_START + 2])[0]

    for flags_length in (root_flags_length, framing_flags_length, dmp_flags_length):
        assert flags_length & 0xF000 == 0x7000

    assert root_flags_length & 0x0FFF == PACKET_SIZE - 16
    assert framing_flags_length & 0x0FFF == PACKET_SIZE - ROOT_LAYER_SIZE
    assert dmp_flags_length & 0x0FFF == DMP_LAYER_SIZE


def test_framing_layer_carries_the_source_name_priority_and_universe() -> None:
    packet = _packet(universe=7, priority=120, sequence=42)

    assert struct.unpack("!I", packet[_FRAMING_START + 2 : _FRAMING_START + 6])[0] == (
        VECTOR_E131_DATA_PACKET
    )
    name = packet[_SOURCE_NAME_AT : _SOURCE_NAME_AT + 64]
    assert len(name) == 64
    assert name.rstrip(b"\x00").decode() == SOURCE_NAME
    assert packet[_PRIORITY_AT] == 120
    assert packet[_SEQUENCE_AT] == 42
    assert packet[_OPTIONS_AT] == 0
    assert struct.unpack("!H", packet[_UNIVERSE_AT : _UNIVERSE_AT + 2])[0] == 7


def test_dmp_layer_addresses_all_512_slots_behind_a_zero_start_code() -> None:
    packet = _packet()

    assert packet[_DMP_START + 2] == VECTOR_DMP_SET_PROPERTY
    assert packet[_DMP_START + 3] == 0xA1
    assert struct.unpack("!H", packet[_DMP_START + 4 : _DMP_START + 6])[0] == 0x0000
    assert struct.unpack("!H", packet[_DMP_START + 6 : _DMP_START + 8])[0] == 0x0001
    assert struct.unpack("!H", packet[_DMP_START + 8 : _DMP_START + 10])[0] == UNIVERSE_SIZE + 1
    assert packet[_START_CODE_AT] == 0x00
    assert len(packet[_SLOTS_AT:]) == UNIVERSE_SIZE


def test_slots_carry_channel_values_in_patch_order() -> None:
    channels = [0] * UNIVERSE_SIZE
    channels[0] = 255
    channels[24] = 128

    slots = _packet(channels=channels)[_SLOTS_AT:]

    assert slots[0] == 255
    assert slots[24] == 128
    assert slots[1] == 0


def test_slots_are_clamped_rather_than_wrapped() -> None:
    slots = _packet(channels=[300, -5, 255, 0])[_SLOTS_AT:]

    assert slots[0] == 255
    assert slots[1] == 0
    assert slots[2] == 255


def test_short_and_long_channel_lists_still_produce_a_full_frame() -> None:
    assert len(_packet(channels=[1, 2, 3])) == PACKET_SIZE
    assert len(_packet(channels=[1] * (UNIVERSE_SIZE + 50))) == PACKET_SIZE


def test_stream_terminated_sets_only_its_own_option_bit() -> None:
    packet = _packet(options=OPTION_STREAM_TERMINATED)

    assert packet[_OPTIONS_AT] == 0x40


def test_source_name_longer_than_the_field_is_truncated_and_null_terminated() -> None:
    packet = _packet(source_name="x" * 200)

    name = packet[_SOURCE_NAME_AT : _SOURCE_NAME_AT + 64]
    assert name[-1] == 0
    assert name.rstrip(b"\x00") == b"x" * 63


@pytest.mark.parametrize(
    "field, value",
    [("universe", 0), ("universe", 64000), ("priority", 201), ("sequence", 256)],
)
def test_out_of_range_header_fields_are_rejected(field: str, value: int) -> None:
    with pytest.raises(ValueError, match=field):
        _packet(**{field: value})


def test_a_cid_must_be_sixteen_bytes() -> None:
    with pytest.raises(ValueError, match="cid"):
        _packet(cid=b"short")


def test_cid_is_stable_for_a_source_name_and_differs_between_sources() -> None:
    assert cid_from_source_name("Lights App") == cid_from_source_name("Lights App")
    assert cid_from_source_name("Lights App") != cid_from_source_name("Other App")
    assert len(cid_from_source_name("Lights App")) == 16


def test_sequence_numbers_increment_per_universe_and_wrap() -> None:
    counter = SequenceCounter()

    assert [counter.next(1) for _ in range(3)] == [0, 1, 2]
    assert counter.next(2) == 0

    for _ in range(252):
        counter.next(1)
    assert counter.next(1) == 255
    assert counter.next(1) == 0
    assert counter.next(2) == 1


def test_multicast_group_is_derived_from_the_universe() -> None:
    assert multicast_host(1) == "239.255.0.1"
    assert multicast_host(256) == "239.255.1.0"


def test_transport_unicasts_a_framed_universe_to_the_configured_host() -> None:
    transport, sock = _transport()
    channels = [0] * UNIVERSE_SIZE
    channels[0] = 200

    transport.send(channels)

    assert len(sock.sent) == 1
    packet, destination = sock.sent[0]
    assert destination == ("192.168.0.50", 5568)
    assert len(packet) == PACKET_SIZE
    assert packet[_SLOTS_AT] == 200
    assert transport.send_count == 1


def test_transport_sends_to_the_universe_group_in_multicast_mode() -> None:
    transport, sock = _transport(multicast=True, bind_address="192.168.0.5")

    transport.send([0] * UNIVERSE_SIZE)

    assert transport.destination == ("239.255.0.1", 5568)
    assert sock.sent[0][1] == ("239.255.0.1", 5568)
    assert sock.bound_to == ("192.168.0.5", 0)
    assert len(sock.options) == 2


def test_transport_binds_the_configured_local_address() -> None:
    transport, sock = _transport(bind_address="192.168.0.5")

    transport.send([0] * UNIVERSE_SIZE)

    assert sock.bound_to == ("192.168.0.5", 0)
    assert sock.options == []


def test_transport_opens_one_socket_and_increments_the_sequence_per_frame() -> None:
    transport, sock = _transport()

    for _ in range(3):
        transport.send([0] * UNIVERSE_SIZE)

    assert [packet[_SEQUENCE_AT] for packet in sock.packets] == [0, 1, 2]
    assert not sock.closed


def test_send_failures_are_swallowed_and_counted() -> None:
    transport, _ = _transport(sock=FakeSocket(fail_on_send=True))

    transport.send([0] * UNIVERSE_SIZE)
    transport.send([0] * UNIVERSE_SIZE)

    assert transport.failure_count == 2
    assert transport.consecutive_failures == 2
    assert transport.send_count == 0


def test_a_socket_that_cannot_be_opened_does_not_raise() -> None:
    transport, sock = _transport(
        sock=FakeSocket(fail_on_bind=True), bind_address="10.0.0.1"
    )

    transport.send([0] * UNIVERSE_SIZE)

    assert sock.sent == []
    assert transport.send_count == 0


def test_close_blacks_out_then_terminates_the_stream_before_closing() -> None:
    transport, sock = _transport()
    transport.send([255] * UNIVERSE_SIZE)

    transport.close()

    assert len(sock.packets) == 3
    blackout, terminated = sock.packets[1], sock.packets[2]
    assert set(blackout[_SLOTS_AT:]) == {0}
    assert blackout[_OPTIONS_AT] == 0
    assert set(terminated[_SLOTS_AT:]) == {0}
    assert terminated[_OPTIONS_AT] == OPTION_STREAM_TERMINATED
    assert sock.closed


def test_close_is_idempotent_and_stops_later_sends() -> None:
    transport, sock = _transport()
    transport.send([0] * UNIVERSE_SIZE)

    transport.close()
    transport.close()
    transport.send([0] * UNIVERSE_SIZE)

    assert len(sock.packets) == 3


def test_close_without_a_socket_sends_nothing() -> None:
    transport, sock = _transport()

    transport.close()

    assert sock.sent == []
    assert not sock.closed


def test_config_defaults_to_e131() -> None:
    transport = build_transport(DMXConfig())
    assert isinstance(transport, E131Transport)
    assert transport.name == "e131"


def test_null_transport_is_still_selectable() -> None:
    assert isinstance(build_transport(DMXConfig(transport="null")), NullTransport)


def test_config_opts_into_e131_explicitly() -> None:
    transport = build_transport(
        DMXConfig(transport="e131", host="192.168.0.50", bind_address="192.168.0.5")
    )

    assert isinstance(transport, E131Transport)
    assert transport.name == "e131"
    assert transport.destination == ("192.168.0.50", 5568)


def test_multicast_config_ignores_the_configured_host() -> None:
    transport = build_transport(DMXConfig(transport="e131", mode="multicast", host="1.2.3.4"))

    assert transport.destination == ("239.255.0.1", 5568)
