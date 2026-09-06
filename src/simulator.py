from src.channel import (
    add_awgn,
    add_wired_noise,
    quantize_wired_signal,
)
from src.line_coding import (
    b8zs_decode,
    b8zs_encode,
    hdb3_decode,
    hdb3_encode,
)
from src.error_control import hamming_decode, hamming_encode
from src.framing import (
    Frame,
    deserialize_frame,
    is_frame_valid,
    serialize_frame,
)
from src.modulation import (
    bpsk_demodulate,
    bpsk_modulate,
    qam16_demodulate,
    qam16_modulate,
)
from src.utils import bits_to_bytes, bytes_to_bits


def _emit_signal(
    signal_callback,
    method: str,
    frame: Frame,
    transmitted_signal,
    received_signal,
    samples_per_bit: int | None = None,
):
    if signal_callback is None:
        return

    if method == "bpsk":
        display_length = min(
            len(transmitted_signal),
            (samples_per_bit or 20) * 12,
        )

    elif method == "qam16":
        display_length = min(
            len(transmitted_signal),
            256,
        )

    else:
        display_length = min(
            len(transmitted_signal),
            180,
        )

    signal_callback(
        {
            "method": method,
            "frame": frame.sequence_number,
            "transmitted_signal": transmitted_signal[:display_length],
            "received_signal": received_signal[:display_length],
            "samples_per_bit": samples_per_bit,
        }
    )


def transmit_frame_bpsk(
    frame: Frame,
    snr_db: float,
    samples_per_bit: int = 100,
    seed=None,
    signal_callback=None,
) -> tuple[Frame | None, int, bool]:
    serialized_frame = serialize_frame(frame)
    frame_bits = bytes_to_bits(serialized_frame)

    encoded_bits = hamming_encode(frame_bits)

    transmitted_signal = bpsk_modulate(
        encoded_bits,
        samples_per_bit,
    )

    received_signal = add_awgn(
        transmitted_signal,
        snr_db,
        seed,
        samples_per_bit=samples_per_bit,
    )

    _emit_signal(
        signal_callback,
        "bpsk",
        frame,
        transmitted_signal,
        received_signal,
        samples_per_bit,
    )

    received_encoded_bits = bpsk_demodulate(
        received_signal,
        samples_per_bit,
    )

    decoded_bits, corrected_errors = hamming_decode(received_encoded_bits)

    received_bytes = bits_to_bytes(decoded_bits)

    try:
        received_frame = deserialize_frame(received_bytes)
    except (IndexError, ValueError):
        return None, corrected_errors, False

    crc_valid = (
        received_frame.sequence_number == frame.sequence_number
        and is_frame_valid(received_frame)
    )

    return received_frame, corrected_errors, crc_valid


def transmit_frame_wired(
    frame: Frame,
    coding_method: str,
    wired_noise_std: float = 0.0,
    seed=None,
    signal_callback=None,
) -> tuple[Frame | None, int, bool]:
    serialized_frame = serialize_frame(frame)
    frame_bits = bytes_to_bits(serialized_frame)

    encoded_bits = hamming_encode(frame_bits)

    if coding_method == "b8zs":
        transmitted_signal = b8zs_encode(encoded_bits)
        decode_signal = b8zs_decode

    elif coding_method == "hdb3":
        transmitted_signal = hdb3_encode(encoded_bits)
        decode_signal = hdb3_decode

    else:
        raise ValueError("Unknown line coding method.")

    received_signal = add_wired_noise(
        transmitted_signal,
        wired_noise_std,
        seed,
    )

    detected_signal = quantize_wired_signal(received_signal)

    _emit_signal(
        signal_callback,
        coding_method,
        frame,
        transmitted_signal,
        received_signal,
    )

    received_encoded_bits = decode_signal(detected_signal)

    decoded_bits, corrected_errors = hamming_decode(received_encoded_bits)

    received_bytes = bits_to_bytes(decoded_bits)

    try:
        received_frame = deserialize_frame(received_bytes)
    except (IndexError, ValueError):
        return None, corrected_errors, False

    crc_valid = (
        received_frame.sequence_number == frame.sequence_number
        and is_frame_valid(received_frame)
    )

    return received_frame, corrected_errors, crc_valid


def transmit_frame_qam16(
    frame: Frame,
    snr_db: float,
    seed=None,
    signal_callback=None,
) -> tuple[Frame | None, int, bool]:
    serialized_frame = serialize_frame(frame)
    frame_bits = bytes_to_bits(serialized_frame)

    encoded_bits = hamming_encode(frame_bits)

    transmitted_symbols = qam16_modulate(encoded_bits)

    received_symbols = add_awgn(
        transmitted_symbols,
        snr_db,
        seed,
    )

    _emit_signal(
        signal_callback,
        "qam16",
        frame,
        transmitted_symbols,
        received_symbols,
    )

    received_encoded_bits = qam16_demodulate(received_symbols)

    decoded_bits, corrected_errors = hamming_decode(received_encoded_bits)

    received_bytes = bits_to_bytes(decoded_bits)

    try:
        received_frame = deserialize_frame(received_bytes)
    except (IndexError, ValueError):
        return None, corrected_errors, False

    crc_valid = (
        received_frame.sequence_number == frame.sequence_number
        and is_frame_valid(received_frame)
    )

    return received_frame, corrected_errors, crc_valid
