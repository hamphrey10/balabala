"""Parquet persistence for large market-history series."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from quant_deriv_ai.core.exceptions import PersistenceError
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame


def write_parquet(frame: pd.DataFrame, path: Path, *, kind: SeriesKind) -> str:
    """Write a normalized frame to Parquet; return SHA-256 of file bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_frame(frame, kind)
    try:
        normalized.to_parquet(path, engine="pyarrow", index=False)
    except Exception as exc:  # noqa: BLE001
        msg = f"failed to write parquet {path}: {exc}"
        raise PersistenceError(msg) from exc
    return content_hash_file(path)


def read_parquet(path: Path, *, kind: SeriesKind) -> pd.DataFrame:
    """Read a Parquet series; empty frame if missing."""
    if not path.is_file():
        return normalize_frame(pd.DataFrame(), kind)
    try:
        frame = pd.read_parquet(path, engine="pyarrow")
    except Exception as exc:  # noqa: BLE001
        msg = f"failed to read parquet {path}: {exc}"
        raise PersistenceError(msg) from exc
    return normalize_frame(frame, kind)


def content_hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash_frame(frame: pd.DataFrame) -> str:
    """Stable hash of frame content (independent of row index)."""
    payload = frame.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
