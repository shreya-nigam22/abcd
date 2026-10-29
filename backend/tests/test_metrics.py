import pandas as pd
from app.main import metrics_frame, parse_records, to_float


def test_parse_records_supports_list_and_data_envelope():
    assert parse_records([{"a": 1}]) == [{"a": 1}]
    assert parse_records({"data": [{"a": 2}]}) == [{"a": 2}]
    assert parse_records({"unexpected": 1}) == []


def test_to_float_rejects_invalid_and_non_finite_values():
    assert to_float("12.5") == 12.5
    assert to_float("not-a-number") is None
    assert to_float("nan") is None


def test_metrics_error_sign_convention():
    actuals = pd.DataFrame({"startTime": [pd.Timestamp("2026-01-01T00:00Z"), pd.Timestamp("2026-01-01T00:30Z")], "actual": [100.0, 80.0]})
    forecasts = pd.DataFrame({"startTime": [pd.Timestamp("2026-01-01T00:00Z"), pd.Timestamp("2026-01-01T00:30Z")], "forecast": [110.0, 70.0], "publishTime": [pd.Timestamp("2025-12-31T17:00Z"), pd.Timestamp("2025-12-31T17:00Z")]})
    result = metrics_frame(actuals, forecasts)
    assert result["error"].tolist() == [10.0, -10.0]
    assert result["absError"].tolist() == [10.0, 10.0]
