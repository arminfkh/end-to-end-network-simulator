import zlib


def calculate_crc(data: bytes) -> int:
    return zlib.crc32(data)


def verify_crc(data: bytes, received_crc: bytes) -> bool:
    expected_crc = calculate_crc(data)
    actual_crc = int.from_bytes(received_crc, "big")

    return expected_crc == actual_crc


def hamming_encode(bits: str) -> str:
    if len(bits) % 8 != 0:
        raise ValueError("Bit string length must be a multiple of 8.")

    encoded_bits = []

    for i in range(0, len(bits), 8):
        data_bits = [int(bit) for bit in bits[i : i + 8]]

        block = [0] * 12
        data_positions = [2, 4, 5, 6, 8, 9, 10, 11]

        for position, bit in zip(data_positions, data_bits):
            block[position] = bit

        block[0] = block[2] ^ block[4] ^ block[6] ^ block[8] ^ block[10]

        block[1] = block[2] ^ block[5] ^ block[6] ^ block[9] ^ block[10]

        block[3] = block[4] ^ block[5] ^ block[6] ^ block[11]

        block[7] = block[8] ^ block[9] ^ block[10] ^ block[11]

        encoded_bits.extend(str(bit) for bit in block)

    return "".join(encoded_bits)


def hamming_decode(encoded_bits: str) -> tuple[str, int]:
    if len(encoded_bits) % 12 != 0:
        raise ValueError("Encoded bit length must be a multiple of 12.")

    decoded_bits = []
    corrected_errors = 0

    for i in range(0, len(encoded_bits), 12):
        block = [int(bit) for bit in encoded_bits[i : i + 12]]

        s1 = block[0] ^ block[2] ^ block[4] ^ block[6] ^ block[8] ^ block[10]

        s2 = block[1] ^ block[2] ^ block[5] ^ block[6] ^ block[9] ^ block[10]

        s4 = block[3] ^ block[4] ^ block[5] ^ block[6] ^ block[11]

        s8 = block[7] ^ block[8] ^ block[9] ^ block[10] ^ block[11]

        error_position = s1 + 2 * s2 + 4 * s4 + 8 * s8

        if 1 <= error_position <= 12:
            block[error_position - 1] ^= 1
            corrected_errors += 1

        data_positions = [2, 4, 5, 6, 8, 9, 10, 11]

        decoded_bits.extend(str(block[position]) for position in data_positions)

    return "".join(decoded_bits), corrected_errors
