def calculate_throughput(
    total_transmitted_bits: int,
    total_ticks: int,
) -> float:
    return total_transmitted_bits / total_ticks


def calculate_goodput(
    useful_bits: int,
    total_ticks: int,
) -> float:
    return useful_bits / total_ticks


def calculate_efficiency(
    goodput: float,
    throughput: float,
) -> float:
    if throughput == 0:
        return 0.0

    return (goodput / throughput) * 100
