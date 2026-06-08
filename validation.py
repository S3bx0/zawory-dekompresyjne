"""Pomocnicze funkcje parsowania wartości wejściowych z pól formularza."""
import math


def parse_float(value: str) -> float:
    """
    Parsuje tekst na float, obsługując przecinek jako separator dziesiętny.

    Raises:
        ValueError: jeśli wartość jest pusta, nieliczbowa, NaN lub nieskończona.
    """
    raw = value.strip().replace(",", ".")
    if not raw:
        raise ValueError("Pusta wartość.")
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError("Wartość musi być liczbą skończoną (bez NaN / inf).")
    return result


def parse_int(value: str) -> int:
    """
    Parsuje tekst na int, obsługując przecinek jako separator dziesiętny.
    Dopuszcza zapis dziesiętny tylko wtedy, gdy wartość jest całkowita
    (np. "4,0" -> 4, ale "4,5" jest błędem).

    Raises:
        ValueError: jeśli wartość jest pusta, nieliczbowa, NaN lub nieskończona.
    """
    result = parse_float(value)
    if not result.is_integer():
        raise ValueError("Wartość musi być liczbą całkowitą.")
    return int(result)
