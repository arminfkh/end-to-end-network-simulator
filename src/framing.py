from dataclasses import dataclass

from src.error_control import calculate_crc, verify_crc

FLAG = 0x7E
ESCAPE = 0x7D
ESCAPE_XOR = 0x20


@dataclass
class Frame:
    sequence_number: int
    payload: bytes
    trailer: bytes = b""


def fragment_data(data: bytes, payload_size: int) -> list[bytes]:
    return [data[i : i + payload_size] for i in range(0, len(data), payload_size)]


def create_frames(data: bytes, payload_size: int) -> list[Frame]:
    payloads = fragment_data(data, payload_size)

    return [
        Frame(sequence_number, payload)
        for sequence_number, payload in enumerate(payloads)
    ]


def byte_stuff(data: bytes) -> bytes:
    stuffed_data = bytearray()

    for byte in data:
        if byte in (FLAG, ESCAPE):
            stuffed_data.append(ESCAPE)
            stuffed_data.append(byte ^ ESCAPE_XOR)
        else:
            stuffed_data.append(byte)

    return bytes(stuffed_data)


def byte_unstuff(data: bytes) -> bytes:
    unstuffed_data = bytearray()
    i = 0

    while i < len(data):
        if data[i] == ESCAPE:
            i += 1
            unstuffed_data.append(data[i] ^ ESCAPE_XOR)
        else:
            unstuffed_data.append(data[i])

        i += 1

    return bytes(unstuffed_data)


def serialize_frame(frame: Frame) -> bytes:
    header = frame.sequence_number.to_bytes(2, "big") + len(frame.payload).to_bytes(
        2, "big"
    )

    frame_data = header + frame.payload
    trailer = calculate_crc(frame_data).to_bytes(4, "big")

    frame_body = frame_data + trailer
    stuffed_body = byte_stuff(frame_body)

    return bytes([FLAG]) + stuffed_body + bytes([FLAG])


def deserialize_frame(data: bytes) -> Frame:
    if data[0] != FLAG or data[-1] != FLAG:
        raise ValueError("Invalid frame boundaries.")

    stuffed_body = data[1:-1]
    frame_body = byte_unstuff(stuffed_body)

    sequence_number = int.from_bytes(
        frame_body[:2],
        "big",
    )

    payload_length = int.from_bytes(
        frame_body[2:4],
        "big",
    )

    payload_start = 4
    payload_end = payload_start + payload_length

    payload = frame_body[payload_start:payload_end]
    trailer = frame_body[payload_end : payload_end + 4]

    return Frame(
        sequence_number,
        payload,
        trailer,
    )


def is_frame_valid(frame: Frame) -> bool:
    header = frame.sequence_number.to_bytes(2, "big") + len(frame.payload).to_bytes(
        2, "big"
    )

    frame_data = header + frame.payload

    return verify_crc(frame_data, frame.trailer)


def reassemble_frames(frames: list[Frame]) -> bytes:
    ordered_frames = sorted(
        frames,
        key=lambda frame: frame.sequence_number,
    )

    return b"".join(frame.payload for frame in ordered_frames)
