def xor_encrypt(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("Key cannot be empty.")

    return bytes(byte ^ key[i % len(key)] for i, byte in enumerate(data))


def xor_decrypt(data: bytes, key: bytes) -> bytes:
    return xor_encrypt(data, key)
