"""Tests for API middleware."""

from __future__ import annotations

from colette.api.middleware import _Bucket


def test_bucket_initialization() -> None:
    bucket = _Bucket(100)
    assert bucket.tokens == 100.0
    assert bucket.last_refill > 0


def test_bucket_defaults() -> None:
    bucket = _Bucket(50)
    assert bucket.tokens == 50.0
