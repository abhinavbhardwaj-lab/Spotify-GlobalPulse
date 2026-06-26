"""Unit tests for dashboard formatting helpers."""

from src.dashboard import _format_streams, _format_followers


def test_format_streams_billions():
    assert _format_streams(1_500_000_000) == "1.50B"


def test_format_streams_millions():
    assert _format_streams(12_500_000) == "12.5M"


def test_format_streams_thousands():
    assert _format_streams(15_500) == "15.5K"


def test_format_followers_millions():
    assert _format_followers(12_500_000) == "12.5M"


def test_format_followers_small():
    assert _format_followers(450) == "450"
