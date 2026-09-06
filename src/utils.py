from pathlib import Path


def text_to_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def bytes_to_text(data: bytes) -> str:
    return data.decode("utf-8")


def bytes_to_bits(data: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in data)


def bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("Bit string length must be a multiple of 8.")

    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def read_file(file_path: str) -> bytes:
    return Path(file_path).expanduser().read_bytes()


def save_recovered_file(
    data: bytes,
    original_path: str,
    output_directory: str = "received_files",
) -> str:
    original_file = Path(original_path).expanduser()
    output_directory_path = Path(output_directory)

    output_directory_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_directory_path / f"recovered_{original_file.name}"

    output_path.write_bytes(data)

    return str(output_path)
