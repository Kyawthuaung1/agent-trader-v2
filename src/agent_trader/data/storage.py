from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable
from .candles import Candle

_FIELDS = ("open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms")
_DEFAULT_PATH = Path("data/raw/candles.csv")


def save_candles(path: str | Path = _DEFAULT_PATH, candles: Iterable[Candle] = ()) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=_FIELDS)
        writer.writeheader()
        for candle in candles:
            writer.writerow({field: getattr(candle, field) for field in _FIELDS})


def load_candles(path: str | Path = _DEFAULT_PATH) -> list[Candle]:
    target = Path(path)
    result: list[Candle] = []
    with target.open("r", newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not set(_FIELDS).issubset(reader.fieldnames):
            raise ValueError("Candle CSV is missing required columns.")
        for line, row in enumerate(reader, 2):
            try:
                result.append(Candle(int(row["open_time_ms"]), float(row["open"]),
                    float(row["high"]), float(row["low"]), float(row["close"]),
                    float(row["volume"]), int(row["close_time_ms"])))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Invalid candle CSV row {line}.") from exc
    return result
