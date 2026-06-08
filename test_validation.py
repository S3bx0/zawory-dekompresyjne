"""Testy jednostkowe dla modułu validation."""
import pytest
import validation


class TestParseFloat:
    def test_integer_string(self):
        assert validation.parse_float("5") == 5.0

    def test_dot_decimal(self):
        assert validation.parse_float("3.14") == pytest.approx(3.14)

    def test_comma_decimal(self):
        assert validation.parse_float("3,14") == pytest.approx(3.14)

    def test_leading_trailing_spaces(self):
        assert validation.parse_float("  2.5  ") == pytest.approx(2.5)

    def test_negative_value(self):
        assert validation.parse_float("-10,5") == pytest.approx(-10.5)

    def test_zero(self):
        assert validation.parse_float("0") == 0.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validation.parse_float("abc")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validation.parse_float("   ")


class TestParseInt:
    def test_plain_integer(self):
        assert validation.parse_int("3") == 3

    def test_integral_float_string(self):
        assert validation.parse_int("2.0") == 2

    def test_fractional_float_raises(self):
        with pytest.raises(ValueError):
            validation.parse_int("2.4")

    def test_comma_decimal_integral(self):
        assert validation.parse_int("4,0") == 4

    def test_comma_decimal_fractional_raises(self):
        with pytest.raises(ValueError):
            validation.parse_int("4,5")

    def test_spaces(self):
        assert validation.parse_int("  7  ") == 7

    def test_negative(self):
        assert validation.parse_int("-2") == -2

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validation.parse_int("xyz")


class TestNaNInf:
    @pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "Infinity"])
    def test_parse_float_rejects_nan_inf(self, value):
        with pytest.raises(ValueError):
            validation.parse_float(value)

    @pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
    def test_parse_int_rejects_nan_inf(self, value):
        with pytest.raises(ValueError):
            validation.parse_int(value)
