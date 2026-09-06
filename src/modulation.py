import numpy as np


def bpsk_modulate(
    bits: str,
    samples_per_bit: int = 50,
    carrier_cycles: int = 2,
) -> np.ndarray:
    time = np.arange(samples_per_bit) / samples_per_bit
    carrier = np.cos(2 * np.pi * carrier_cycles * time)

    signal = []

    for bit in bits:
        symbol = 1 if bit == "1" else -1
        signal.extend(symbol * carrier)

    return np.array(signal)


def bpsk_demodulate(
    signal: np.ndarray,
    samples_per_bit: int = 50,
    carrier_cycles: int = 2,
) -> str:
    time = np.arange(samples_per_bit) / samples_per_bit
    carrier = np.cos(2 * np.pi * carrier_cycles * time)

    recovered_bits = []

    for i in range(0, len(signal), samples_per_bit):
        bit_signal = signal[i : i + samples_per_bit]
        correlation = np.sum(bit_signal * carrier)

        recovered_bits.append("1" if correlation >= 0 else "0")

    return "".join(recovered_bits)


QAM_BITS_TO_LEVEL = {
    "00": -3,
    "01": -1,
    "11": 1,
    "10": 3,
}

QAM_LEVEL_TO_BITS = {
    -3: "00",
    -1: "01",
    1: "11",
    3: "10",
}


def qam16_modulate(bits: str) -> np.ndarray:
    symbols = []

    for i in range(0, len(bits), 4):
        bit_group = bits[i : i + 4]

        i_level = QAM_BITS_TO_LEVEL[bit_group[:2]]
        q_level = QAM_BITS_TO_LEVEL[bit_group[2:]]

        symbols.append(complex(i_level, q_level))

    return np.array(symbols)


def qam16_demodulate(symbols: np.ndarray) -> str:
    levels = np.array([-3, -1, 1, 3])
    recovered_bits = []

    for symbol in symbols:
        i_level = levels[np.argmin(np.abs(levels - symbol.real))]

        q_level = levels[np.argmin(np.abs(levels - symbol.imag))]

        recovered_bits.append(
            QAM_LEVEL_TO_BITS[int(i_level)] + QAM_LEVEL_TO_BITS[int(q_level)]
        )

    return "".join(recovered_bits)
