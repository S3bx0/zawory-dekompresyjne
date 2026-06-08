import math
import pytest
from obliczenia import (
    calculate_decompression_valves,
    CalculationResult,
    K,
    ZAWORY,
    V_MAX,
    F_MAX,
    TEMP_MAX,
    TEMP_MIN,
)


# ── Testy poprawnych obliczeń (wzór producenta, bez zaokrąglania pośredniego) ─
@pytest.mark.parametrize(
    "V, tp, tz, F, typ",
    [
        (150, -25, -27, 25000, "Maxi Elebar"),
        (150, -25, -27, 25000, "Maxi Elebar EVO-VERTICAL"),
        (500, -30, -35, 10000, "Maxi Elebar"),
        (100, -20, -20.5, 50000, "Maxi Elebar"),
        # Komora dodatnia (chiller) — wzór producenta nie wymaga temperatur ujemnych
        (200, 5, 2, 8000, "Maxi Elebar"),
    ],
    ids=["elebar-standard", "evo-vertical", "large-room", "small-delta", "positive-chiller"],
)
def test_formula_matches_producer(V, tp, tz, F, typ):
    """Weryfikacja wzoru: Δt = (F/V · DT1)/60 ; Q = K · V · Δt (bez zaokrągleń pośrednich)."""
    result = calculate_decompression_valves(V, tp, tz, F, typ)
    expected_dT = (F / V * (tp - tz)) / 60.0
    expected_Q = K * V * expected_dT
    assert isinstance(result, CalculationResult)
    assert result.delta_T == pytest.approx(expected_dT, rel=1e-12)
    assert result.Q == pytest.approx(expected_Q, rel=1e-12)
    assert result.ilosc_zaworow == math.ceil(expected_Q / ZAWORY[typ])
    assert result.przeplyw_zaworu == ZAWORY[typ]
    assert result.typ_zaworu == typ


def test_producer_example_safety_margin():
    """
    Przykład z karty producenta: V=1200, F=32000, DT1=2.2 °C.

    Karta producenta podaje 3 zawory EVO — ale z zaokrągleniem Δt do 2 miejsc (0.97).
    Bez zaokrągleń pośrednich: Δt=0.9778, Q=4294.4, 4294.4/1430=3.003 → ceil=4.

    Świadomie dajemy 4 zawory (margines bezpieczeństwa): różnica wynika z niejawnego
    zaokrąglenia w karcie producenta. W krytycznej aplikacji wyrównania ciśnienia
    lepiej przewymiarować niż niedomiarować.
    """
    result = calculate_decompression_valves(
        V=1200, temp_przed=-23.0, temp_za=-25.2, F=32000,
        typ_zaworu="Maxi Elebar EVO-VERTICAL",
    )
    assert result.delta_T == pytest.approx(0.9778, abs=1e-3)
    assert result.Q == pytest.approx(4294.4, abs=1.0)
    assert result.ilosc_zaworow == 4


# ── Testy błędnych danych wejściowych ─────────────────────────────────────
@pytest.mark.parametrize(
    "V, tp, tz, F, exc_type",
    [
        (0, -25, -27, 25000, ValueError),
        (-1, -25, -27, 25000, ValueError),
        (150, -25, -27, -25000, ValueError),
        (150, -25, -27, 0, ValueError),
        (150, -25, -25, 25000, ValueError),
        (150, -27, -25, 25000, ValueError),
    ],
    ids=["zero-volume", "negative-volume", "negative-flow", "zero-flow",
         "equal-temps", "reversed-temps"],
)
def test_error_cases(V, tp, tz, F, exc_type):
    with pytest.raises(exc_type):
        calculate_decompression_valves(V, tp, tz, F)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_rejected(bad_value):
    with pytest.raises(ValueError):
        calculate_decompression_valves(bad_value, -25, -27, 25000)
    with pytest.raises(ValueError):
        calculate_decompression_valves(150, bad_value, -27, 25000)
    with pytest.raises(ValueError):
        calculate_decompression_valves(150, -25, bad_value, 25000)
    with pytest.raises(ValueError):
        calculate_decompression_valves(150, -25, -27, bad_value)


def test_tiny_valid_volume():
    result = calculate_decompression_valves(0.0001, -25, -27, 25000)
    assert result.ilosc_zaworow >= 1


def test_unknown_valve_type():
    with pytest.raises(KeyError):
        calculate_decompression_valves(150, -25, -27, 25000, "Nieznany Zawór")


def test_result_is_frozen():
    result = calculate_decompression_valves(150, -25, -27, 25000)
    with pytest.raises(Exception):
        result.delta_T = 999  # type: ignore[misc]


def test_result_fields_complete():
    result = calculate_decompression_valves(150, -25, -27, 25000)
    assert result.przeplyw_zaworu == ZAWORY["Maxi Elebar"]
    assert result.typ_zaworu == "Maxi Elebar"


def test_no_intermediate_rounding_regression():
    """
    Regresja: Q jest liczone z surowego Δt (bez zaokrągleń pośrednich).
    Q = K · V · delta_T_raw.
    """
    result = calculate_decompression_valves(123.45, -25.7, -28.3, 27890.5)
    assert result.Q == pytest.approx(K * 123.45 * result.delta_T, rel=1e-12)


# ── Sanity-check: limity górne (wykrywanie literówek) ─────────────────────
class TestSanityLimits:
    def test_volume_too_large(self):
        with pytest.raises(ValueError, match="literówka"):
            calculate_decompression_valves(V_MAX + 1, -25, -27, 25000)

    def test_volume_at_limit_ok(self):
        # Na granicy — musi przejść
        result = calculate_decompression_valves(V_MAX, -25, -27, 25000)
        assert result.ilosc_zaworow >= 1

    def test_flow_too_large(self):
        with pytest.raises(ValueError, match="literówka"):
            calculate_decompression_valves(150, -25, -27, F_MAX + 1)

    @pytest.mark.parametrize("temp", [TEMP_MAX + 1, TEMP_MIN - 1])
    def test_temp_out_of_range(self, temp):
        with pytest.raises(ValueError, match="poza zakresem"):
            calculate_decompression_valves(150, temp, temp - 2, 25000)
        with pytest.raises(ValueError, match="poza zakresem"):
            calculate_decompression_valves(150, 10, temp, 25000)

    def test_temp_at_limits_ok(self):
        # Skrajne wartości w granicach — muszą przejść
        result = calculate_decompression_valves(150, TEMP_MAX, TEMP_MIN, 25000)
        assert result.ilosc_zaworow >= 1
