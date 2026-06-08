"""
Rdzeń obliczeniowy kalkulatora zaworów dekompresyjnych.

Wzory pochodzą z karty doboru producenta zaworów (Maxi Elebar / EVO-VERTICAL):

    Δt = (F / V * DT1) / 60      [°C/min]
    Q  = K * V * Δt              [l/min]
    n  = ceil(Q / Q_zaworu)      [szt.]

gdzie:
    K     – współczynnik producenta, stała = 3.66
    V     – kubatura komory [m³]
    F     – całkowity przepływ powietrza przez chłodnicę/chłodnice [m³/h]
    DT1   – różnica temperatur powietrza przed i za chłodnicą [°C]
            (w kodzie: temp_przed - temp_za, wymagane > 0)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# ── Stałe producenta ───────────────────────────────────────────────────────
K: float = 3.66  # współczynnik producenta (karta doboru Maxi Elebar)

ZAWORY: dict[str, int] = {
    "Maxi Elebar": 4300,               # l/min — stropowy
    "Maxi Elebar EVO-VERTICAL": 1430,  # l/min — stropowy
}

# ── Limity sanity-check (wykrywanie literówek i nierealnych danych) ───────
V_MAX: float = 1_000_000.0        # [m³]  — hala wielkości stadionu
F_MAX: float = 10_000_000.0       # [m³/h] — wentylatory przemysłowe ciężkie
TEMP_MIN: float = -200.0          # [°C]  — hel ciekły ≈ -269; -200 to twardy limit
TEMP_MAX: float = 200.0           # [°C]  — komory chłodnicze nie mają tak gorąco


@dataclass(frozen=True)
class CalculationResult:
    """Niemutowalny wynik obliczeń zaworów dekompresyjnych."""
    delta_T: float        # [°C/min] — surowa wartość (bez zaokrągleń w środku obliczeń)
    Q: float              # [l/min]
    ilosc_zaworow: int    # [szt.]
    przeplyw_zaworu: int  # [l/min] — wydatek pojedynczego zaworu
    typ_zaworu: str = ""  # nazwa typu zaworu


def _is_finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


def calculate_decompression_valves(
    V: float,
    temp_przed: float,
    temp_za: float,
    F: float,
    typ_zaworu: str = "Maxi Elebar",
) -> CalculationResult:
    """
    Oblicza parametry zaworów dekompresyjnych wg karty producenta.

    Args:
        V: Objętość komory [m³], > 0.
        temp_przed: Temperatura przed chłodnicą [°C].
        temp_za: Temperatura za chłodnicą [°C]. Wymagane: temp_przed > temp_za.
        F: Całkowity przepływ powietrza przez chłodnicę/chłodnice [m³/h], > 0.
        typ_zaworu: Klucz ze słownika ZAWORY.

    Returns:
        CalculationResult z polami delta_T, Q, ilosc_zaworow, przeplyw_zaworu, typ_zaworu.

    Raises:
        ValueError: dane wejściowe nieliczbowe, NaN, inf lub poza zakresem.
        KeyError: nieznany typ zaworu.
    """
    if not _is_finite(V, temp_przed, temp_za, F):
        raise ValueError("Dane wejściowe zawierają NaN lub nieskończoność.")
    if V <= 0:
        raise ValueError("Objętość komory musi być większa od zera.")
    if V > V_MAX:
        raise ValueError(f"Objętość komory > {V_MAX:,.0f} m³ — prawdopodobnie literówka.")
    if F <= 0:
        raise ValueError("Przepływ powietrza musi być większy od zera.")
    if F > F_MAX:
        raise ValueError(f"Przepływ powietrza > {F_MAX:,.0f} m³/h — prawdopodobnie literówka.")
    if not (TEMP_MIN <= temp_przed <= TEMP_MAX):
        raise ValueError(
            f"Temperatura przed wlotem poza zakresem [{TEMP_MIN}..{TEMP_MAX}] °C."
        )
    if not (TEMP_MIN <= temp_za <= TEMP_MAX):
        raise ValueError(
            f"Temperatura za wlotem poza zakresem [{TEMP_MIN}..{TEMP_MAX}] °C."
        )
    if temp_przed == temp_za:
        raise ValueError("Temperatura przed i za chłodnicą muszą być różne (DT1 = 0).")
    if temp_przed < temp_za:
        raise ValueError(
            "Temperatura przed chłodnicą musi być wyższa niż za chłodnicą "
            "(chłodnica schładza powietrze)."
        )

    przeplyw_zaworu = ZAWORY[typ_zaworu]  # KeyError gdy nieznany typ

    DT1 = temp_przed - temp_za
    delta_T = (F / V * DT1) / 60.0       # [°C/min] — bez zaokrąglania pośredniego
    Q = K * V * delta_T                   # [l/min]
    ilosc_zaworow = math.ceil(Q / przeplyw_zaworu)

    # UWAGA metodologiczna:
    # Karta producenta w przykładzie zaokrągla Δt w dół do 2 miejsc (0.9778 → 0.97),
    # co systematycznie zaniża Q i może dawać o 1 zawór mniej. Z punktu widzenia
    # bezpieczeństwa (wyrównywanie ciśnienia — krytyczne dla konstrukcji komory)
    # liczymy bez zaokrągleń pośrednich. math.ceil na końcu zapewnia margines.

    return CalculationResult(
        delta_T=delta_T,
        Q=Q,
        ilosc_zaworow=ilosc_zaworow,
        przeplyw_zaworu=przeplyw_zaworu,
        typ_zaworu=typ_zaworu,
    )
