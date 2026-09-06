import numpy as np

from src.framing import Frame, serialize_frame
from src.simulator import (
    transmit_frame_bpsk,
    transmit_frame_qam16,
    transmit_frame_wired,
)


def selective_repeat_wireless(
    frames: list[Frame],
    window_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    modulation_method: str,
    samples_per_bit: int = 50,
    max_attempts: int = 10,
    seed=None,
    return_status: bool = False,
    event_callback=None,
    signal_callback=None,
) -> tuple:
    random_generator = np.random.default_rng(seed)

    base = 0
    next_sequence = 0
    tick = 0

    acked_frames = set()
    received_frames = {}

    attempts = {frame.sequence_number: 0 for frame in frames}

    deadlines = {}
    pending_naks = set()

    logs = []
    retransmissions = 0
    total_corrected_blocks = 0
    total_transmitted_bits = 0
    failed_frame = None

    def add_log(message: str):
        logs.append(message)

        if event_callback is not None:
            event_callback(message)

    def mark_frame_failed(sequence_number: int):
        nonlocal failed_frame

        failed_frame = sequence_number
        deadlines.pop(sequence_number, None)
        pending_naks.discard(sequence_number)

        add_log(
            f"[Tick {tick}] Maximum attempts reached for frame " f"{sequence_number}"
        )

    def send_frame(sequence_number: int):
        nonlocal retransmissions
        nonlocal total_corrected_blocks
        nonlocal total_transmitted_bits

        attempts[sequence_number] += 1
        attempt = attempts[sequence_number]

        if attempt == 1:
            action = "SEND"
        else:
            action = "RETRANSMIT"
            retransmissions += 1

        deadlines[sequence_number] = tick + timeout_ticks

        add_log(
            f"[Tick {tick}] {action} frame " f"{sequence_number} (attempt {attempt})"
        )

        serialized_frame = serialize_frame(frames[sequence_number])

        transmitted_bits = len(serialized_frame) * 12
        total_transmitted_bits += transmitted_bits

        if random_generator.random() < loss_rate:
            add_log(f"[Tick {tick}] Frame " f"{sequence_number} lost")

            if signal_callback is not None:
                signal_callback(
                    {
                        "method": modulation_method,
                        "frame": sequence_number,
                        "attempt": attempt,
                        "lost": True,
                    }
                )

            if attempt >= max_attempts:
                mark_frame_failed(sequence_number)

            return

        channel_seed = int(
            random_generator.integers(
                0,
                2**32 - 1,
            )
        )

        def frame_signal_callback(signal_data: dict):
            if signal_callback is None:
                return

            signal_data = signal_data.copy()
            signal_data["attempt"] = attempt
            signal_callback(signal_data)

        if modulation_method == "bpsk":
            (
                received_frame,
                corrected_blocks,
                crc_valid,
            ) = transmit_frame_bpsk(
                frames[sequence_number],
                snr_db,
                samples_per_bit,
                channel_seed,
                signal_callback=frame_signal_callback,
            )

        elif modulation_method == "qam16":
            (
                received_frame,
                corrected_blocks,
                crc_valid,
            ) = transmit_frame_qam16(
                frames[sequence_number],
                snr_db,
                channel_seed,
                signal_callback=frame_signal_callback,
            )

        else:
            raise ValueError("Unknown modulation method.")

        total_corrected_blocks += corrected_blocks

        add_log(f"[Tick {tick}] Hamming corrected blocks: " f"{corrected_blocks}")

        if crc_valid:
            received_frames[sequence_number] = received_frame

            acked_frames.add(sequence_number)
            deadlines.pop(sequence_number, None)

            add_log(f"[Tick {tick}] ACK " f"{sequence_number}")

        else:
            add_log(f"[Tick {tick}] CRC failed for frame " f"{sequence_number}")

            add_log(f"[Tick {tick}] NAK " f"{sequence_number}")

            if attempt >= max_attempts:
                mark_frame_failed(sequence_number)
            else:
                pending_naks.add(sequence_number)

    while len(acked_frames) < len(frames) and failed_frame is None:
        window_end = min(base + window_size - 1, len(frames) - 1)

        add_log(f"[Tick {tick}] Sender window: " f"{base} to {window_end}")

        retransmit_now = set(pending_naks)
        pending_naks.clear()

        for sequence_number, deadline in list(deadlines.items()):
            if (
                sequence_number not in acked_frames
                and deadline <= tick
                and sequence_number not in retransmit_now
            ):
                add_log(f"[Tick {tick}] TIMEOUT " f"{sequence_number}")

                retransmit_now.add(sequence_number)

        for sequence_number in sorted(retransmit_now):
            send_frame(sequence_number)

            if failed_frame is not None:
                break

        if failed_frame is not None:
            break

        while next_sequence < len(frames) and next_sequence < base + window_size:
            send_frame(next_sequence)
            next_sequence += 1

            if failed_frame is not None:
                break

        if failed_frame is not None:
            break

        while base < len(frames) and base in acked_frames:
            base += 1

        tick += 1

    ordered_frames = [
        received_frames[sequence_number] for sequence_number in sorted(received_frames)
    ]

    transmission_completed = len(acked_frames) == len(frames)
    total_ticks = tick + 1 if failed_frame is not None else tick

    result = (
        ordered_frames,
        logs,
        total_ticks,
        retransmissions,
        total_corrected_blocks,
        total_transmitted_bits,
        transmission_completed,
        failed_frame,
    )

    if return_status:
        return result

    return result[:6]


def selective_repeat_bpsk(
    frames: list[Frame],
    window_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    samples_per_bit: int = 20,
    max_attempts: int = 10,
    seed=None,
    return_status: bool = False,
    event_callback=None,
    signal_callback=None,
) -> tuple:
    return selective_repeat_wireless(
        frames=frames,
        window_size=window_size,
        timeout_ticks=timeout_ticks,
        snr_db=snr_db,
        loss_rate=loss_rate,
        modulation_method="bpsk",
        samples_per_bit=samples_per_bit,
        max_attempts=max_attempts,
        seed=seed,
        return_status=return_status,
        event_callback=event_callback,
        signal_callback=signal_callback,
    )


def selective_repeat_qam16(
    frames: list[Frame],
    window_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    max_attempts: int = 10,
    seed=None,
    return_status: bool = False,
    event_callback=None,
    signal_callback=None,
) -> tuple:
    return selective_repeat_wireless(
        frames=frames,
        window_size=window_size,
        timeout_ticks=timeout_ticks,
        snr_db=snr_db,
        loss_rate=loss_rate,
        modulation_method="qam16",
        max_attempts=max_attempts,
        seed=seed,
        return_status=return_status,
        event_callback=event_callback,
        signal_callback=signal_callback,
    )


def selective_repeat_wired(
    frames: list[Frame],
    window_size: int,
    timeout_ticks: int,
    coding_method: str,
    wired_noise_std: float,
    loss_rate: float,
    max_attempts: int = 10,
    seed=None,
    return_status: bool = False,
    event_callback=None,
    signal_callback=None,
) -> tuple:
    random_generator = np.random.default_rng(seed)

    base = 0
    next_sequence = 0
    tick = 0

    acked_frames = set()
    received_frames = {}

    attempts = {frame.sequence_number: 0 for frame in frames}

    deadlines = {}
    pending_naks = set()

    logs = []
    retransmissions = 0
    total_corrected_blocks = 0
    total_transmitted_bits = 0
    failed_frame = None

    def add_log(message: str):
        logs.append(message)

        if event_callback is not None:
            event_callback(message)

    def mark_frame_failed(sequence_number: int):
        nonlocal failed_frame

        failed_frame = sequence_number
        deadlines.pop(sequence_number, None)
        pending_naks.discard(sequence_number)

        add_log(
            f"[Tick {tick}] Maximum attempts reached for frame " f"{sequence_number}"
        )

    def send_frame(sequence_number: int):
        nonlocal retransmissions
        nonlocal total_corrected_blocks
        nonlocal total_transmitted_bits

        attempts[sequence_number] += 1
        attempt = attempts[sequence_number]

        if attempt == 1:
            action = "SEND"
        else:
            action = "RETRANSMIT"
            retransmissions += 1

        deadlines[sequence_number] = tick + timeout_ticks

        add_log(
            f"[Tick {tick}] {action} frame " f"{sequence_number} (attempt {attempt})"
        )

        serialized_frame = serialize_frame(frames[sequence_number])

        transmitted_bits = len(serialized_frame) * 12
        total_transmitted_bits += transmitted_bits

        if random_generator.random() < loss_rate:
            add_log(f"[Tick {tick}] Frame " f"{sequence_number} lost")

            if signal_callback is not None:
                signal_callback(
                    {
                        "method": coding_method,
                        "frame": sequence_number,
                        "attempt": attempt,
                        "lost": True,
                    }
                )

            if attempt >= max_attempts:
                mark_frame_failed(sequence_number)

            return

        channel_seed = int(
            random_generator.integers(
                0,
                2**32 - 1,
            )
        )

        def frame_signal_callback(signal_data: dict):
            if signal_callback is None:
                return

            signal_data = signal_data.copy()
            signal_data["attempt"] = attempt
            signal_callback(signal_data)

        (
            received_frame,
            corrected_blocks,
            crc_valid,
        ) = transmit_frame_wired(
            frames[sequence_number],
            coding_method=coding_method,
            wired_noise_std=wired_noise_std,
            seed=channel_seed,
            signal_callback=frame_signal_callback,
        )

        total_corrected_blocks += corrected_blocks

        add_log(f"[Tick {tick}] Hamming corrected blocks: " f"{corrected_blocks}")

        if crc_valid:
            received_frames[sequence_number] = received_frame

            acked_frames.add(sequence_number)
            deadlines.pop(sequence_number, None)

            add_log(f"[Tick {tick}] ACK " f"{sequence_number}")

        else:
            add_log(f"[Tick {tick}] CRC failed for frame " f"{sequence_number}")

            add_log(f"[Tick {tick}] NAK " f"{sequence_number}")

            if attempt >= max_attempts:
                mark_frame_failed(sequence_number)
            else:
                pending_naks.add(sequence_number)

    while len(acked_frames) < len(frames) and failed_frame is None:
        window_end = min(
            base + window_size - 1,
            len(frames) - 1,
        )

        add_log(f"[Tick {tick}] Sender window: " f"{base} to {window_end}")

        retransmit_now = set(pending_naks)
        pending_naks.clear()

        for sequence_number, deadline in list(deadlines.items()):
            if (
                sequence_number not in acked_frames
                and deadline <= tick
                and sequence_number not in retransmit_now
            ):
                add_log(f"[Tick {tick}] TIMEOUT " f"{sequence_number}")

                retransmit_now.add(sequence_number)

        for sequence_number in sorted(retransmit_now):
            send_frame(sequence_number)

            if failed_frame is not None:
                break

        if failed_frame is not None:
            break

        while next_sequence < len(frames) and next_sequence < base + window_size:
            send_frame(next_sequence)
            next_sequence += 1

            if failed_frame is not None:
                break

        if failed_frame is not None:
            break

        while base < len(frames) and base in acked_frames:
            base += 1

        tick += 1

    ordered_frames = [
        received_frames[sequence_number] for sequence_number in sorted(received_frames)
    ]

    transmission_completed = len(acked_frames) == len(frames)
    total_ticks = tick + 1 if failed_frame is not None else tick

    result = (
        ordered_frames,
        logs,
        total_ticks,
        retransmissions,
        total_corrected_blocks,
        total_transmitted_bits,
        transmission_completed,
        failed_frame,
    )

    if return_status:
        return result

    return result[:6]
