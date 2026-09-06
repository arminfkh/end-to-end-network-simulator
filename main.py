from pathlib import Path

from src.framing import create_frames, reassemble_frames, serialize_frame
from src.metrics import (
    calculate_efficiency,
    calculate_goodput,
    calculate_throughput,
)
from src.security import xor_decrypt, xor_encrypt
from src.selective_repeat import (
    selective_repeat_bpsk,
    selective_repeat_qam16,
    selective_repeat_wired,
)
from src.utils import (
    bytes_to_text,
    read_file,
    save_recovered_file,
    text_to_bytes,
)


def choose_input() -> tuple[
    str,
    bytes,
    str,
    str | None,
]:
    while True:
        print("Choose input type:")
        print("1. Text")
        print("2. File")

        input_choice = input("Enter choice: ").strip()

        if input_choice == "1":
            message = input("Enter message: ")

            if not message:
                message = "NETWORK SIMULATION"

            return (
                "text",
                text_to_bytes(message),
                message,
                None,
            )

        if input_choice == "2":
            file_path = input("Enter file path: ").strip()

            file_path = file_path.strip("\"'")

            file = Path(file_path).expanduser()

            if file.is_file():
                return (
                    "file",
                    read_file(str(file)),
                    file.name,
                    str(file),
                )

            print()
            print("File not found. Try again.")
            print()

        else:
            print()
            print("Invalid choice. Try again.")
            print()


def choose_transmission_method() -> str:
    while True:
        print("Choose channel type:")
        print("1. Wired")
        print("2. Wireless")

        channel_choice = input("Enter choice: ").strip()

        if channel_choice == "1":
            print()
            print("Choose line coding:")
            print("1. B8ZS")
            print("2. HDB3")

            coding_choice = input("Enter choice: ").strip()

            if coding_choice == "1":
                return "b8zs"

            if coding_choice == "2":
                return "hdb3"

        elif channel_choice == "2":
            print()
            print("Choose modulation:")
            print("1. BPSK")
            print("2. 16-QAM")

            modulation_choice = input("Enter choice: ").strip()

            if modulation_choice == "1":
                return "bpsk"

            if modulation_choice == "2":
                return "qam16"

        print()
        print("Invalid choice. Try again.")
        print()


def run_transmission(
    frames,
    transmission_method: str,
    window_size: int,
    timeout_ticks: int,
    max_attempts: int,
    loss_rate: float,
    wired_noise_std: float,
    bpsk_snr_db: float,
    qam16_snr_db: float,
    samples_per_bit: int,
    seed: int,
):
    if transmission_method in (
        "b8zs",
        "hdb3",
    ):
        return selective_repeat_wired(
            frames,
            window_size=window_size,
            timeout_ticks=timeout_ticks,
            coding_method=transmission_method,
            wired_noise_std=wired_noise_std,
            loss_rate=loss_rate,
            max_attempts=max_attempts,
            seed=seed,
            return_status=True,
        )

    if transmission_method == "bpsk":
        return selective_repeat_bpsk(
            frames,
            window_size=window_size,
            timeout_ticks=timeout_ticks,
            snr_db=bpsk_snr_db,
            loss_rate=loss_rate,
            samples_per_bit=samples_per_bit,
            max_attempts=max_attempts,
            seed=seed,
            return_status=True,
        )

    return selective_repeat_qam16(
        frames,
        window_size=window_size,
        timeout_ticks=timeout_ticks,
        snr_db=qam16_snr_db,
        loss_rate=loss_rate,
        max_attempts=max_attempts,
        seed=seed,
        return_status=True,
    )


def main():
    key = b"network-key"

    text_payload_size = 4
    file_payload_size = 256

    window_size = 4
    timeout_ticks = 3
    max_attempts = 10

    loss_rate = 0.0
    wired_noise_std = 0.0

    bpsk_snr_db = 20
    qam16_snr_db = 25
    samples_per_bit = 20

    seed = 42

    print("=== End-to-End Network Simulator ===")
    print()

    (
        input_type,
        original_data,
        input_name,
        original_file_path,
    ) = choose_input()

    if not original_data:
        print()
        print("Input data is empty.")
        return

    if input_type == "text":
        payload_size = text_payload_size
    else:
        payload_size = file_payload_size

    print()

    transmission_method = choose_transmission_method()

    encrypted_data = xor_encrypt(
        original_data,
        key,
    )

    frames = create_frames(
        encrypted_data,
        payload_size,
    )

    (
        received_frames,
        logs,
        total_ticks,
        retransmissions,
        corrected_blocks,
        total_transmitted_bits,
        transmission_completed,
        failed_frame,
    ) = run_transmission(
        frames=frames,
        transmission_method=transmission_method,
        window_size=window_size,
        timeout_ticks=timeout_ticks,
        max_attempts=max_attempts,
        loss_rate=loss_rate,
        wired_noise_std=wired_noise_std,
        bpsk_snr_db=bpsk_snr_db,
        qam16_snr_db=qam16_snr_db,
        samples_per_bit=samples_per_bit,
        seed=seed,
    )

    for log in logs:
        print(log)

    if not transmission_completed:
        print()
        print("--- TRANSMISSION RESULT ---")
        print("Method:", transmission_method.upper())
        print("Input type:", input_type.capitalize())
        print("Input:", input_name)
        print(
            "Received frames:",
            [frame.sequence_number for frame in received_frames],
        )
        print("Failed frame:", failed_frame)

        print()
        print("--- FINAL STATUS ---")
        print("Transmission incomplete")
        return

    received_encrypted_data = reassemble_frames(received_frames)

    recovered_data = xor_decrypt(
        received_encrypted_data,
        key,
    )

    transmission_successful = (
        received_encrypted_data == encrypted_data and recovered_data == original_data
    )

    recovered_message = None
    recovered_file_path = None

    if input_type == "text":
        recovered_message = bytes_to_text(recovered_data)

    elif transmission_successful:
        recovered_file_path = save_recovered_file(
            recovered_data,
            original_file_path,
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

    efficiency = calculate_efficiency(
        goodput,
        throughput,
    )

    print()
    print("--- TRANSMISSION RESULT ---")
    print(
        "Method:",
        transmission_method.upper(),
    )

    print(
        "Input type:",
        input_type.capitalize(),
    )

    if input_type == "text":
        print(
            "Original message:",
            input_name,
        )

        print(
            "Recovered message:",
            recovered_message,
        )

        print(
            "Encrypted bytes:",
            encrypted_data.hex(" "),
        )

        print(
            "Received encrypted bytes:",
            received_encrypted_data.hex(" "),
        )

    else:
        print(
            "Original file:",
            input_name,
        )

        print(
            "Original file size:",
            len(original_data),
            "bytes",
        )

        print(
            "Recovered file size:",
            len(recovered_data),
            "bytes",
        )

        if recovered_file_path is not None:
            print(
                "Recovered file saved to:",
                recovered_file_path,
            )

    print()
    print("--- SIMULATION SETTINGS ---")
    print(
        "Payload size:",
        payload_size,
    )

    print(
        "Window size:",
        window_size,
    )

    print(
        "Timeout ticks:",
        timeout_ticks,
    )

    print(
        "Maximum attempts per frame:",
        max_attempts,
    )

    print(
        "Loss rate:",
        loss_rate,
    )

    if transmission_method in (
        "b8zs",
        "hdb3",
    ):
        print("Channel type: Wired")

        print(
            "Wired noise standard deviation:",
            wired_noise_std,
        )

    elif transmission_method == "bpsk":
        print("Channel type: Wireless")

        print(
            "SNR:",
            bpsk_snr_db,
            "dB",
        )

        print(
            "Samples per bit:",
            samples_per_bit,
        )

    else:
        print("Channel type: Wireless")

        print(
            "SNR:",
            qam16_snr_db,
            "dB",
        )

    print()
    print("--- SIMULATION STATISTICS ---")
    print(
        "Total frames:",
        len(frames),
    )

    print(
        "Total ticks:",
        total_ticks,
    )

    print(
        "Retransmissions:",
        retransmissions,
    )

    print(
        "Total corrected Hamming blocks:",
        corrected_blocks,
    )

    print(
        "Total transmitted bits:",
        total_transmitted_bits,
    )

    print(f"Throughput: " f"{throughput:.2f} bits/tick")

    print(f"Goodput: " f"{goodput:.2f} bits/tick")

    print(f"Efficiency: " f"{efficiency:.2f}%")

    print()
    print("--- FINAL STATUS ---")

    if transmission_successful:
        print("Transmission successful")
    else:
        print("Transmission failed")


if __name__ == "__main__":
    main()
