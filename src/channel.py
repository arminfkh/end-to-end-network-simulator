import numpy as np


def add_awgn(
    signal: np.ndarray,
    snr_db: float,
    seed=None,
    samples_per_bit: int | None = None,
) -> np.ndarray:
    random_generator = np.random.default_rng(seed)
    snr_linear = 10 ** (snr_db / 10)

    if np.iscomplexobj(signal):
        signal_power = np.mean(np.abs(signal) ** 2)
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / 2)

        noise = random_generator.normal(
            0,
            noise_std,
            size=signal.shape,
        ) + 1j * random_generator.normal(
            0,
            noise_std,
            size=signal.shape,
        )

    else:
        if samples_per_bit is None:
            signal_power = np.mean(signal**2)
            noise_power = signal_power / snr_linear
            noise_std = np.sqrt(noise_power)
        else:
            bit_energy = np.sum(signal[:samples_per_bit] ** 2)
            noise_variance = bit_energy / (2 * snr_linear)
            noise_std = np.sqrt(noise_variance)

        noise = random_generator.normal(
            0,
            noise_std,
            size=signal.shape,
        )

    return signal + noise


def add_wired_noise(
    signal: list[int],
    noise_std: float,
    seed=None,
) -> list[float]:
    random_generator = np.random.default_rng(seed)

    noise = random_generator.normal(
        0,
        noise_std,
        size=len(signal),
    )

    received_signal = np.array(signal, dtype=float) + noise

    return received_signal.tolist()


def quantize_wired_signal(
    signal: list[float],
    threshold: float = 0.5,
) -> list[int]:
    decoded_levels = []

    for sample in signal:
        if sample > threshold:
            decoded_levels.append(1)
        elif sample < -threshold:
            decoded_levels.append(-1)
        else:
            decoded_levels.append(0)

    return decoded_levels
