"""
Supabase integration for persisting alerts and checking duplicates.

Table schema (create this in Supabase SQL editor):

    CREATE TABLE alerts (
        id           BIGSERIAL PRIMARY KEY,
        asset        TEXT NOT NULL,
        timeframe    TEXT NOT NULL,
        pattern      TEXT NOT NULL,
        type         TEXT NOT NULL,
        confidence   NUMERIC(5,2) NOT NULL,
        price        NUMERIC(20,8) NOT NULL,
        detected_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        message_sent BOOLEAN NOT NULL DEFAULT FALSE,
        key_levels   JSONB,
        pattern_data JSONB
    );

    CREATE INDEX idx_alerts_lookup
        ON alerts (asset, timeframe, pattern, detected_at DESC);
    CREATE INDEX idx_alerts_asset_time
        ON alerts (asset, detected_at DESC);
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def _get_client() -> Optional[Client]:
    # Support both os.environ (scanner/GH Actions) and st.secrets (Streamlit)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    # Try Streamlit secrets if env vars not set
    if not url or not key:
        try:
            import streamlit as st
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_KEY")
        except Exception:
            pass

    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set – Supabase disabled")
        return None
    try:
        return create_client(url, key)
    except Exception as exc:
        logger.error("Failed to create Supabase client: %s", exc)
        return None


_client: Optional[Client] = None


def get_client() -> Optional[Client]:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


def _retry_db(func, *args, max_attempts: int = 3, **kwargs):
    delays = [2, 4, 8]
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_attempts - 1:
                raise
            logger.warning("DB attempt %d/%d failed: %s", attempt + 1, max_attempts, exc)
            time.sleep(delays[attempt])


def is_duplicate(
    asset: str,
    timeframe: str,
    pattern: str,
    cooldown_hours: int = 24,
) -> bool:
    """Returns True if the same pattern was alerted within the cooldown period."""
    client = get_client()
    if client is None:
        logger.warning("Supabase unavailable – skipping duplicate check")
        return False

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()

    try:
        def _query():
            return (
                client.table("alerts")
                .select("id, detected_at")
                .eq("asset", asset)
                .eq("timeframe", timeframe)
                .eq("pattern", pattern)
                .gte("detected_at", cutoff)
                .limit(1)
                .execute()
            )

        response = _retry_db(_query)
        return len(response.data) > 0

    except Exception as exc:
        logger.error("Duplicate check failed: %s – treating as new alert", exc)
        return False


def save_alert(
    asset: str,
    timeframe: str,
    pattern: str,
    signal_type: str,
    confidence: float,
    price: float,
    message_sent: bool = False,
    key_levels: Optional[dict] = None,
    pattern_data: Optional[dict] = None,
) -> Optional[int]:
    """Persist a new alert to Supabase. Returns the inserted record id or None."""
    client = get_client()
    record = {
        "asset": asset,
        "timeframe": timeframe,
        "pattern": pattern,
        "type": signal_type,
        "confidence": round(confidence, 2),
        "price": round(price, 8),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "message_sent": message_sent,
        "key_levels": key_levels or {},
        "pattern_data": pattern_data or {},
    }

    if client is None:
        logger.info("ALERT (no DB): %s", record)
        return None

    try:
        def _insert():
            return client.table("alerts").insert(record).execute()

        response = _retry_db(_insert)
        if response.data:
            inserted_id = response.data[0].get("id")
            logger.info("Alert saved to Supabase: id=%s", inserted_id)
            return inserted_id
    except Exception as exc:
        logger.error("Failed to save alert: %s – record: %s", exc, record)

    return None


def mark_message_sent(alert_id: int) -> None:
    """Update message_sent flag after successful Telegram send."""
    client = get_client()
    if client is None or alert_id is None:
        return
    try:
        def _update():
            return (
                client.table("alerts")
                .update({"message_sent": True})
                .eq("id", alert_id)
                .execute()
            )
        _retry_db(_update)
    except Exception as exc:
        logger.error("Failed to mark message_sent for id=%s: %s", alert_id, exc)


def get_recent_alerts(limit: int = 10, asset: Optional[str] = None) -> list[dict]:
    """Fetch the most recent alerts, optionally filtered by asset."""
    client = get_client()
    if client is None:
        return []
    try:
        def _fetch():
            q = (
                client.table("alerts")
                .select("*")
                .order("detected_at", desc=True)
                .limit(limit)
            )
            if asset:
                q = q.eq("asset", asset)
            return q.execute()
        response = _retry_db(_fetch)
        return response.data or []
    except Exception as exc:
        logger.error("Failed to fetch recent alerts: %s", exc)
        return []


def get_alerts_for_asset(
    asset: str,
    timeframe: Optional[str] = None,
    pattern: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """Fetch alerts for a specific asset with optional filters."""
    client = get_client()
    if client is None:
        return []
    try:
        def _fetch():
            q = (
                client.table("alerts")
                .select("*")
                .eq("asset", asset)
                .order("detected_at", desc=True)
                .limit(limit)
            )
            if timeframe:
                q = q.eq("timeframe", timeframe)
            if pattern:
                q = q.eq("pattern", pattern)
            if date_from:
                q = q.gte("detected_at", date_from)
            if date_to:
                q = q.lte("detected_at", date_to)
            return q.execute()
        response = _retry_db(_fetch)
        return response.data or []
    except Exception as exc:
        logger.error("Failed to fetch alerts for asset %s: %s", asset, exc)
        return []


def get_alerts_last_n_days(asset: str, days: int = 7) -> list[dict]:
    """Fetch alerts for an asset from the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return get_alerts_for_asset(asset, date_from=cutoff)


def get_run_stats() -> dict:
    """Return stats for /status command."""
    client = get_client()
    if client is None:
        return {"runs_today": 0, "last_run": "N/A"}

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    try:
        def _fetch():
            return (
                client.table("alerts")
                .select("detected_at")
                .gte("detected_at", today)
                .order("detected_at", desc=True)
                .limit(100)
                .execute()
            )
        response = _retry_db(_fetch)
        data = response.data or []
        last_run = data[0]["detected_at"] if data else "N/A"
        return {"runs_today": len(data), "last_run": last_run}
    except Exception as exc:
        logger.error("Failed to get run stats: %s", exc)
        return {"runs_today": 0, "last_run": "N/A"}
