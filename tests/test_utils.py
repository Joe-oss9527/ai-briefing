"""Tests for utility helpers."""

import datetime as dt

from briefing.utils import parse_datetime_safe, now_utc


def test_parse_datetime_safe_iso_z():
    raw = "2024-10-16T04:39:38.000Z"
    parsed = parse_datetime_safe(raw)
    assert parsed is not None
    assert parsed.tzinfo == dt.timezone.utc
    assert parsed.isoformat() == "2024-10-16T04:39:38+00:00"


def test_parse_datetime_safe_with_offset():
    raw = "2024-10-16T06:39:38+02:00"
    parsed = parse_datetime_safe(raw)
    assert parsed is not None
    # Convert to UTC and compare expected instant (04:39:38Z)
    assert parsed.tzinfo == dt.timezone.utc
    assert parsed.isoformat() == "2024-10-16T04:39:38+00:00"


def test_parse_datetime_safe_rfc2822():
    raw = "Wed, 05 Jun 2024 12:30:00 +0000"
    parsed = parse_datetime_safe(raw)
    assert parsed is not None
    assert parsed.isoformat() == "2024-06-05T12:30:00+00:00"


def test_parse_datetime_safe_invalid_returns_none():
    assert parse_datetime_safe("not-a-date") is None
    assert parse_datetime_safe("") is None
    assert parse_datetime_safe(None) is None



def test_now_utc_returns_timezone_aware():
    now = now_utc()
    assert now.tzinfo == dt.timezone.utc
