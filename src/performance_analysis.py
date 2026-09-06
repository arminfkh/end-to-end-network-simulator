from pathlib import Path

import matplotlib.pyplot as plt

from src.framing import create_frames, serialize_frame
from src.metrics import calculate_goodput, calculate_throughput
from src.security import xor_encrypt
from src.selective_repeat import selective_repeat_bpsk
from src.utils import text_to_bytes


def run_bpsk_simulation(
    message: str,
    key: bytes,
    payload_size: int,
    window_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    samples_per_bit: int,
    seed: int,
    max_attempts: int,
) -> tuple[float, float]:
    original_data = text_to_bytes(message)
    encrypted_data = xor_encrypt(original_data, key)

    frames = create_frames(
        encrypted_data,
        payload_size,
    )

    (
        received_frames,
        _,
        total_ticks,
        _,
        _,
        _,
        _,
        _,
    ) = selective_repeat_bpsk(
        frames,
        window_size=window_size,
        timeout_ticks=timeout_ticks,
        snr_db=snr_db,
        loss_rate=loss_rate,
        samples_per_bit=samples_per_bit,
        max_attempts=max_attempts,
        seed=seed,
        return_status=True,
    )

    delivered_channel_bits = sum(
        len(serialize_frame(frame)) * 12 for frame in received_frames
    )

    useful_bits = sum(len(frame.payload) * 8 for frame in received_frames)

    throughput = calculate_throughput(
        delivered_channel_bits,
        total_ticks,
    )

    goodput = calculate_goodput(
        useful_bits,
        total_ticks,
    )

    return throughput, goodput


def average_bpsk_simulation(
    message: str,
    key: bytes,
    payload_size: int,
    window_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    samples_per_bit: int,
    runs: int,
    base_seed: int,
    max_attempts: int,
) -> tuple[float, float]:
    throughput_sum = 0.0
    goodput_sum = 0.0

    for run_index in range(runs):
        throughput, goodput = run_bpsk_simulation(
            message=message,
            key=key,
            payload_size=payload_size,
            window_size=window_size,
            timeout_ticks=timeout_ticks,
            snr_db=snr_db,
            loss_rate=loss_rate,
            samples_per_bit=samples_per_bit,
            seed=base_seed + run_index,
            max_attempts=max_attempts,
        )

        throughput_sum += throughput
        goodput_sum += goodput

    return (
        throughput_sum / runs,
        goodput_sum / runs,
    )


def analyze_snr_values(
    message: str,
    key: bytes,
    snr_values: list[float],
    payload_size: int,
    window_size: int,
    timeout_ticks: int,
    samples_per_bit: int,
    runs: int,
    base_seed: int,
    max_attempts: int,
) -> tuple[list[float], list[float]]:
    throughput_values = []
    goodput_values = []

    for snr_db in snr_values:
        throughput, goodput = average_bpsk_simulation(
            message=message,
            key=key,
            payload_size=payload_size,
            window_size=window_size,
            timeout_ticks=timeout_ticks,
            snr_db=snr_db,
            loss_rate=0.0,
            samples_per_bit=samples_per_bit,
            runs=runs,
            base_seed=base_seed,
            max_attempts=max_attempts,
        )

        print(f"SNR={snr_db} dB")

        throughput_values.append(throughput)
        goodput_values.append(goodput)

    return throughput_values, goodput_values


def analyze_window_sizes(
    message: str,
    key: bytes,
    window_sizes: list[int],
    payload_size: int,
    timeout_ticks: int,
    snr_db: float,
    loss_rate: float,
    samples_per_bit: int,
    runs: int,
    base_seed: int,
    max_attempts: int,
) -> tuple[list[float], list[float]]:
    throughput_values = []
    goodput_values = []

    for window_size in window_sizes:
        throughput, goodput = average_bpsk_simulation(
            message=message,
            key=key,
            payload_size=payload_size,
            window_size=window_size,
            timeout_ticks=timeout_ticks,
            snr_db=snr_db,
            loss_rate=loss_rate,
            samples_per_bit=samples_per_bit,
            runs=runs,
            base_seed=base_seed,
            max_attempts=max_attempts,
        )

        throughput_values.append(throughput)
        goodput_values.append(goodput)

    return throughput_values, goodput_values


def plot_performance(
    x_values: list,
    throughput_values: list[float],
    goodput_values: list[float],
    title: str,
    x_label: str,
    output_path: str,
):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 5))

    plt.plot(
        x_values,
        throughput_values,
        marker="o",
        label="Throughput",
    )

    plt.plot(
        x_values,
        goodput_values,
        marker="s",
        label="Goodput",
    )

    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel("Delivered bits per tick")
    plt.xticks(x_values)
    plt.ylim(bottom=0)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.savefig(
        path,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()
