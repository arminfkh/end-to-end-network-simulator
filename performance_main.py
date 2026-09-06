from src.performance_analysis import (
    analyze_snr_values,
    analyze_window_sizes,
    plot_performance,
)


def print_results(title, first_column, x_values, throughput_values, goodput_values):
    print()
    print(title)
    print(f"{first_column:<15}{'Throughput':<20}{'Goodput':<20}")

    for value, throughput, goodput in zip(
        x_values,
        throughput_values,
        goodput_values,
    ):
        print(f"{value:<15}{throughput:<20.2f}{goodput:<20.2f}")


def main():
    message = "Computer networks end-to-end simulation. " * 10
    key = b"network-key"

    payload_size = 16
    timeout_ticks = 3
    samples_per_bit = 20
    max_attempts = 30
    runs = 20

    snr_values = [2, 3, 4, 5, 6, 7, 8]

    snr_throughput, snr_goodput = analyze_snr_values(
        message=message,
        key=key,
        snr_values=snr_values,
        payload_size=payload_size,
        window_size=4,
        timeout_ticks=timeout_ticks,
        samples_per_bit=samples_per_bit,
        runs=runs,
        base_seed=100,
        max_attempts=max_attempts,
    )

    window_sizes = [1, 2, 4, 8]

    window_throughput, window_goodput = analyze_window_sizes(
        message=message,
        key=key,
        window_sizes=window_sizes,
        payload_size=payload_size,
        timeout_ticks=timeout_ticks,
        snr_db=6,
        loss_rate=0.05,
        samples_per_bit=samples_per_bit,
        runs=runs,
        base_seed=1000,
        max_attempts=max_attempts,
    )

    print_results(
        "--- SNR ANALYSIS ---",
        "SNR (dB)",
        snr_values,
        snr_throughput,
        snr_goodput,
    )

    print_results(
        "--- WINDOW SIZE ANALYSIS ---",
        "Window Size",
        window_sizes,
        window_throughput,
        window_goodput,
    )

    plot_performance(
        snr_values,
        snr_throughput,
        snr_goodput,
        "SNR Effect on Throughput and Goodput",
        "SNR (dB)",
        "docs/figures/snr_performance.png",
    )

    plot_performance(
        window_sizes,
        window_throughput,
        window_goodput,
        "Window Size Effect on Throughput and Goodput",
        "Window Size",
        "docs/figures/window_performance.png",
    )

    print()
    print("Performance plots saved.")


if __name__ == "__main__":
    main()
