def b8zs_encode(bits: str) -> list[int]:
    signal = []
    last_pulse = -1
    i = 0

    while i < len(bits):
        if bits[i : i + 8] == "00000000":
            signal.extend(
                [
                    0,
                    0,
                    0,
                    last_pulse,
                    -last_pulse,
                    0,
                    -last_pulse,
                    last_pulse,
                ]
            )
            i += 8

        elif bits[i] == "1":
            last_pulse *= -1
            signal.append(last_pulse)
            i += 1

        else:
            signal.append(0)
            i += 1

    return signal


def hdb3_encode(bits: str) -> list[int]:
    signal = []
    last_pulse = -1
    pulse_count = 0
    i = 0

    while i < len(bits):
        if bits[i : i + 4] == "0000":
            if pulse_count % 2 == 0:
                bipolar_pulse = -last_pulse
                violation_pulse = bipolar_pulse

                signal.extend(
                    [
                        bipolar_pulse,
                        0,
                        0,
                        violation_pulse,
                    ]
                )

                last_pulse = violation_pulse

            else:
                violation_pulse = last_pulse

                signal.extend(
                    [
                        0,
                        0,
                        0,
                        violation_pulse,
                    ]
                )

            pulse_count = 0
            i += 4

        elif bits[i] == "1":
            last_pulse *= -1
            signal.append(last_pulse)
            pulse_count += 1
            i += 1

        else:
            signal.append(0)
            i += 1

    return signal


def b8zs_decode(signal: list[int]) -> str:
    bits = []
    last_pulse = -1
    i = 0

    while i < len(signal):
        substitution = [
            0,
            0,
            0,
            last_pulse,
            -last_pulse,
            0,
            -last_pulse,
            last_pulse,
        ]

        if signal[i : i + 8] == substitution:
            bits.extend(["0"] * 8)
            i += 8

        elif signal[i] == 0:
            bits.append("0")
            i += 1

        else:
            bits.append("1")
            last_pulse = signal[i]
            i += 1

    return "".join(bits)


def hdb3_decode(signal: list[int]) -> str:
    bits = []
    last_pulse = -1
    pulse_count = 0
    i = 0

    while i < len(signal):
        even_pulse_count = pulse_count % 2 == 0

        if even_pulse_count:
            bipolar_pulse = -last_pulse
            substitution = [
                bipolar_pulse,
                0,
                0,
                bipolar_pulse,
            ]
        else:
            substitution = [
                0,
                0,
                0,
                last_pulse,
            ]

        if signal[i : i + 4] == substitution:
            bits.extend(["0"] * 4)

            if even_pulse_count:
                last_pulse = bipolar_pulse

            pulse_count = 0
            i += 4

        elif signal[i] == 0:
            bits.append("0")
            i += 1

        else:
            bits.append("1")
            last_pulse = signal[i]
            pulse_count += 1
            i += 1

    return "".join(bits)
