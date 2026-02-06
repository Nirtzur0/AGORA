"""
High-signal assertion helpers for contract/range/completeness checks.

Goal: when these fail, the message should make debugging fast (what failed, where,
expected constraint, observed stats, and a small sample of offenders).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import is_dataclass, asdict
import math
from typing import Any, Iterable, Mapping, Sequence


def _to_mapping(obj: Any) -> Mapping[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    # pydantic/dataclass-like
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()  # type: ignore[no-any-return]
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return obj.model_dump()  # type: ignore[no-any-return]
    # Last resort: public attrs
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    raise TypeError(f"Unsupported object type for mapping conversion: {type(obj)!r}")


def _get_field(obj: Any, field: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(field)
    return getattr(obj, field, None)


def _sample(items: Sequence[Any], n: int = 5) -> list[Any]:
    return list(items[:n])


def assert_required_fields(obj: Any, fields: Iterable[str], *, context: str = "") -> None:
    m = _to_mapping(obj)
    missing = [f for f in fields if f not in m]
    if missing:
        ctx = f" context={context!r}" if context else ""
        raise AssertionError(f"Missing required fields{ctx}: {missing}. Present keys={sorted(m.keys())}")


def assert_non_null_fields(obj: Any, fields: Iterable[str], *, context: str = "") -> None:
    m = _to_mapping(obj)
    nulls = [f for f in fields if f in m and m.get(f) is None]
    if nulls:
        ctx = f" context={context!r}" if context else ""
        raise AssertionError(f"Required fields are null{ctx}: {nulls}.")


def assert_missing_rate(
    rows: Sequence[Any],
    field: str,
    max_rate: float,
    *,
    context: str = "",
    missing_values: set[Any] | None = None,
) -> None:
    if not 0 <= max_rate <= 1:
        raise ValueError(f"max_rate must be in [0, 1], got {max_rate}")
    missing_values = missing_values or {None}

    total = len(rows)
    if total == 0:
        raise AssertionError(f"No rows provided for missingness check on {field!r}.")

    missing_idxs: list[int] = []
    for i, row in enumerate(rows):
        if _get_field(row, field) in missing_values:
            missing_idxs.append(i)

    rate = len(missing_idxs) / total
    if rate > max_rate:
        ctx = f" context={context!r}" if context else ""
        offenders = _sample(missing_idxs, 10)
        raise AssertionError(
            f"Missingness too high for field={field!r}{ctx}: "
            f"missing_rate={rate:.3f} (missing={len(missing_idxs)}/{total}) > max_rate={max_rate:.3f}. "
            f"missing_row_indexes(sample)={offenders}"
        )


def assert_in_range(
    values: Any,
    *,
    min: float | None = None,  # noqa: A002 (min is intentional API)
    max: float | None = None,  # noqa: A002
    allow_nan: bool = False,
    context: str = "",
) -> None:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        seq = [values]
    else:
        seq = list(values)

    bad: list[tuple[int, Any]] = []
    numeric: list[float] = []
    for i, v in enumerate(seq):
        if v is None:
            bad.append((i, v))
            continue
        try:
            fv = float(v)
        except Exception:
            bad.append((i, v))
            continue
        if math.isnan(fv):
            if not allow_nan:
                bad.append((i, v))
            continue
        numeric.append(fv)
        if min is not None and fv < min:
            bad.append((i, v))
        if max is not None and fv > max:
            bad.append((i, v))

    if bad:
        ctx = f" context={context!r}" if context else ""
        numeric_min = min(numeric) if numeric else None
        numeric_max = max(numeric) if numeric else None
        raise AssertionError(
            f"Values out of range{ctx}: expected "
            f"{'min=' + str(min) if min is not None else ''}"
            f"{', ' if min is not None and max is not None else ''}"
            f"{'max=' + str(max) if max is not None else ''}. "
            f"observed_min={numeric_min} observed_max={numeric_max}. "
            f"bad(sample)={_sample(bad, 10)}"
        )


def assert_allowed_values(values: Iterable[Any], allowed: set[Any], *, context: str = "") -> None:
    vals = list(values)
    unexpected = [v for v in vals if v not in allowed]
    if unexpected:
        ctx = f" context={context!r}" if context else ""
        counts = Counter(unexpected)
        raise AssertionError(
            f"Unexpected categorical values{ctx}: unexpected_counts={dict(counts)} allowed(sample)={_sample(sorted(allowed), 20)}"
        )


def assert_unique(values: Iterable[Any], *, context: str = "") -> None:
    vals = list(values)
    counts = Counter(vals)
    dups = [(v, c) for v, c in counts.items() if c > 1]
    if dups:
        ctx = f" context={context!r}" if context else ""
        raise AssertionError(f"Expected unique values{ctx}, found duplicates(sample)={_sample(sorted(dups, key=lambda x: -x[1]), 20)}")


def assert_probability_vector(vec: Sequence[Any], *, tol: float = 1e-6, context: str = "") -> None:
    if not vec:
        raise AssertionError("Probability vector is empty.")
    floats: list[float] = []
    for v in vec:
        try:
            floats.append(float(v))
        except Exception:
            raise AssertionError(f"Probability vector contains non-numeric value: {v!r}")

    assert_in_range(floats, min=0.0, max=1.0, context=context)
    s = sum(floats)
    if abs(s - 1.0) > tol:
        ctx = f" context={context!r}" if context else ""
        raise AssertionError(f"Probability vector must sum to 1{ctx}: sum={s} tol={tol} vec(sample)={_sample(floats, 20)}")

