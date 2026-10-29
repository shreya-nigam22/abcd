from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "WindSight | Wind Forecast Intelligence"
ELEXON_BASE = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000")

app = FastAPI(title=APP_NAME, version="1.0.0", description="Wind generation forecast accuracy explorer using Elexon FUELHH and WINDFOR datasets.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in FRONTEND_ORIGINS.split(",") if x.strip()] + ["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def parse_records(payload: Any) -> list[dict[str, Any]]:
    """Normalize common Elexon JSON response envelopes to a list of records."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "records"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
    return []


async def fetch_dataset(dataset: str, params: dict[str, str]) -> list[dict[str, Any]]:
    url = f"{ELEXON_BASE}/datasets/{dataset}/stream"
    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0), follow_redirects=True) as client:
        response = await client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        try:
            return parse_records(response.json())
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"Elexon returned an unexpected response for {dataset}.") from exc


def first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return None


def to_float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if np.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def to_utc(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts
    except Exception:
        return None


def actual_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rec in records:
        fuel = str(first(rec, "fuelType", "fueltype", "fuel_type") or "").upper()
        if fuel and fuel != "WIND":
            continue
        ts = to_utc(first(rec, "startTime", "settlementDateTime", "start_time"))
        generation = to_float(first(rec, "generation", "quantity", "generationMW"))
        if ts is not None and generation is not None:
            rows.append({"startTime": ts, "actual": generation})
    if not rows:
        return pd.DataFrame(columns=["startTime", "actual"])
    df = pd.DataFrame(rows).groupby("startTime", as_index=False)["actual"].sum()
    return df


def forecast_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rec in records:
        ts = to_utc(first(rec, "startTime", "settlementDateTime", "start_time"))
        published = to_utc(first(rec, "publishTime", "publicationTime", "publish_time"))
        generation = to_float(first(rec, "generation", "quantity", "generationMW"))
        if ts is not None and generation is not None:
            rows.append({"startTime": ts, "publishTime": published, "forecast": generation})
    if not rows:
        return pd.DataFrame(columns=["startTime", "publishTime", "forecast"])
    df = pd.DataFrame(rows)
    # Preserve the full forecast vintage history. If publication time is missing, keep it null.
    return df.drop_duplicates(subset=["startTime", "publishTime", "forecast"])


async def load_month(year: int, month: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    # Elexon dataset stream uses settlement-date filters for FUELHH and publication-time
    # filters for forecast vintages. Fetch a broad publication window around the target month.
    actual_params = {"settlementDateFrom": start.isoformat(), "settlementDateTo": end.isoformat(), "format": "json"}
    publish_from = (datetime(start.year, start.month, start.day, tzinfo=timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    publish_to = (datetime(end.year, end.month, end.day, 23, 59, tzinfo=timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    forecast_params = {"publishDateTimeFrom": publish_from, "publishDateTimeTo": publish_to, "format": "json"}
    errors: list[str] = []
    actual_records: list[dict[str, Any]] = []
    forecast_records: list[dict[str, Any]] = []
    try:
        actual_records = await fetch_dataset("FUELHH", actual_params)
    except Exception as exc:
        errors.append(f"FUELHH: {str(exc)[:180]}")
    try:
        forecast_records = await fetch_dataset("WINDFOR", forecast_params)
    except Exception as exc:
        errors.append(f"WINDFOR: {str(exc)[:180]}")
    return actual_frame(actual_records), forecast_frame(forecast_records), {"actual_records": len(actual_records), "forecast_records": len(forecast_records), "errors": errors}


def choose_decision_forecast(forecasts: pd.DataFrame, decision_day: date) -> pd.DataFrame:
    """For each delivery interval, choose latest forecast published before its prior-day decision cut-off.

    Cut-off is defined transparently as 17:00 UTC on the day before delivery. This is an
    explicit product assumption, not a claim about the client's exact trading workflow.
    """
    if forecasts.empty:
        return pd.DataFrame(columns=["startTime", "forecast", "publishTime"])
    f = forecasts.copy()
    f = f[f["startTime"].dt.date >= decision_day]
    f["cutoff"] = f["startTime"].dt.floor("D") - pd.Timedelta(days=1) + pd.Timedelta(hours=17)
    f = f[f["publishTime"].notna() & (f["publishTime"] <= f["cutoff"])]
    if f.empty:
        return pd.DataFrame(columns=["startTime", "forecast", "publishTime"])
    f = f.sort_values(["startTime", "publishTime"])
    return f.groupby("startTime", as_index=False).tail(1)[["startTime", "forecast", "publishTime"]]


def metrics_frame(actuals: pd.DataFrame, forecasts: pd.DataFrame) -> pd.DataFrame:
    if actuals.empty or forecasts.empty:
        return pd.DataFrame(columns=["startTime", "actual", "forecast", "error", "absError", "sqError", "publishTime"])
    merged = actuals.merge(forecasts, on="startTime", how="inner")
    if merged.empty:
        return merged
    merged["error"] = merged["forecast"] - merged["actual"]
    merged["absError"] = merged["error"].abs()
    merged["sqError"] = merged["error"] ** 2
    return merged.sort_values("startTime")


def json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]) or col in ("startTime", "publishTime"):
            out[col] = out[col].map(lambda x: x.isoformat().replace("+00:00", "Z") if pd.notna(x) else None)
    out = out.replace({np.nan: None})
    return out.to_dict(orient="records")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.get("/api/analysis")
async def analysis(
    year: int = Query(2026, ge=2020, le=2035),
    month: int = Query(1, ge=1, le=12),
    view: str = Query("latest", pattern="^(latest|day-ahead)$"),
) -> dict[str, Any]:
    try:
        actuals, all_forecasts, meta = await load_month(year, month)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to retrieve Elexon data: {exc}") from exc
    if actuals.empty and all_forecasts.empty:
        return {"period": f"{year:04d}-{month:02d}", "view": view, "source": "Elexon Insights API", "dataStatus": "unavailable", "message": "No usable records were returned by Elexon. Check API availability and try again.", "metrics": {}, "records": [], "forecastPublicationCount": 0, "metadata": meta}

    # The latest vintage is useful for retrospective exploration. The day-ahead view applies
    # the stated prior-day 17:00 UTC decision cutoff to prevent future information leakage.
    if view == "day-ahead":
        selected = choose_decision_forecast(all_forecasts, date(year, month, 1))
        # Restrict records to requested delivery month after selecting a valid vintage.
        selected = selected[selected["startTime"].map(lambda t: t.year == year and t.month == month)] if not selected.empty else selected
    else:
        selected = all_forecasts.sort_values("publishTime").groupby("startTime", as_index=False).tail(1) if not all_forecasts.empty else all_forecasts
        selected = selected[selected["startTime"].map(lambda t: t.year == year and t.month == month)] if not selected.empty else selected
    month_actuals = actuals[actuals["startTime"].map(lambda t: t.year == year and t.month == month)] if not actuals.empty else actuals
    joined = metrics_frame(month_actuals, selected)
    metrics: dict[str, Any] = {}
    if not joined.empty:
        metrics = {
            "matchedIntervals": int(len(joined)),
            "maeMw": round(float(joined["absError"].mean()), 2),
            "rmseMw": round(float(np.sqrt(joined["sqError"].mean())), 2),
            "biasMw": round(float(joined["error"].mean()), 2),
            "meanActualMw": round(float(joined["actual"].mean()), 2),
            "meanForecastMw": round(float(joined["forecast"].mean()), 2),
            "overForecastIntervals": int((joined["error"] > 0).sum()),
            "underForecastIntervals": int((joined["error"] < 0).sum()),
        }
    # Show forecast-only points too, since the buyer needs to inspect the forecast before actuals exist.
    display = selected.merge(month_actuals, on="startTime", how="left") if not selected.empty else pd.DataFrame()
    if not display.empty:
        display["error"] = display["forecast"] - display["actual"]
    return {
        "period": f"{year:04d}-{month:02d}",
        "view": view,
        "source": "Elexon Insights API (FUELHH actuals, WINDFOR forecasts)",
        "dataStatus": "live",
        "message": None if not joined.empty else "Forecast/actual overlap is not available for this selection yet. Forecast records may still be displayed.",
        "metrics": metrics,
        "records": json_records(display[[c for c in ["startTime", "actual", "forecast", "publishTime", "error"] if c in display.columns]]) if not display.empty else [],
        "forecastPublicationCount": int(all_forecasts["publishTime"].nunique()) if not all_forecasts.empty else 0,
        "metadata": meta,
        "methodology": {"dayAheadCutoff": "17:00 UTC on the day before delivery", "errorDefinition": "forecast - actual; positive means over-forecast", "note": "Cut-off is an explicit modelling assumption and can be adjusted to match the client's actual trading deadline."},
    }


@app.get("/api/metadata")
async def metadata() -> dict[str, Any]:
    return {
        "datasets": [
            {"code": "FUELHH", "purpose": "Half-hourly actual generation by fuel type; records filtered to WIND."},
            {"code": "WINDFOR", "purpose": "Wind generation forecast vintages, including publication time."},
        ],
        "apiBase": ELEXON_BASE,
        "apiKeyRequired": False,
        "officialDocumentation": "https://bmrs.elexon.co.uk/api-documentation/endpoint",
    }
