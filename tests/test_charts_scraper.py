"""Unit tests for the kworb scraper."""

from src.charts_scraper import _to_int, ArtistStreamRow


def test_to_int_parses_thousands_separator():
    assert _to_int("1,234,567") == 1234567


def test_to_int_handles_blank():
    assert _to_int("") == 0
    assert _to_int("-") == 0


def test_to_int_handles_negative():
    assert _to_int("-12,345") == -12345


def test_artist_stream_row_serializes():
    row = ArtistStreamRow(rank=1, name="Bad Bunny", daily_streams=12_000_000, total_streams=1_000_000_000)
    assert row.to_dict()["rank"] == 1
    assert row.to_dict()["name"] == "Bad Bunny"
