"""Evaluate register *field specs* against attribute tables.

A field spec is either ``null``, a column name, or a mapping:

``{field: X}`` plus optional transforms applied in this order:
``floordiv: N`` (integer division), ``slice: [a, b]`` (string slice), ``zfill: N``,
``map: {old: new}``, ``regex_sub: [pattern, replacement]``, ``case: title|upper|lower``;
or ``{template: "{A}{B}"}`` (Python format over columns), or ``{value: "constant"}``.

Values are normalised to strings (integral floats lose their ``.0``; blanks become None).
"""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

FieldSpec = str | dict[str, Any] | None


def to_str(v: object) -> str | None:
    """Normalise a scalar to a clean string (None for null/blank)."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        if v.is_integer():
            return str(int(v))
    s = str(v).replace("\r", " ").replace("\n", " ").strip()
    return s or None


def columns_of(spec: FieldSpec) -> set[str]:
    """Attribute columns a spec reads."""
    if spec is None:
        return set()
    if isinstance(spec, str):
        return {spec}
    if "field" in spec:
        return {spec["field"]}
    if "template" in spec:
        return set(re.findall(r"{(\w+)", spec["template"]))
    return set()


def evaluate(df: pd.DataFrame, spec: FieldSpec) -> pd.Series | None:
    """Evaluate a field spec, returning a string Series aligned to ``df`` (or None for a null spec)."""
    if spec is None:
        return None
    missing = columns_of(spec) - set(df.columns)
    if missing:
        raise KeyError(
            f"field(s) {sorted(missing)} not in layer columns {list(df.columns)}"
        )
    if isinstance(spec, str):
        return df[spec].map(to_str)
    if "value" in spec:
        return pd.Series(
            [to_str(spec["value"])] * len(df), index=df.index, dtype=object
        )
    if "template" in spec:
        tpl = spec["template"]
        cols = columns_of(spec)
        return df.apply(
            lambda r: tpl.format(**{c: to_str(r[c]) or "" for c in cols}), axis=1
        ).map(to_str)
    s = df[spec["field"]]
    if "floordiv" in spec:
        n = spec["floordiv"]
        s = pd.to_numeric(s, errors="coerce").map(
            lambda v: None if pd.isna(v) else int(v) // n
        )
    s = s.map(to_str)
    if "slice" in spec:
        a, b = spec["slice"]
        s = s.map(lambda v: None if v is None else v[a:b])
    if "zfill" in spec:
        s = s.map(lambda v: None if v is None else v.zfill(spec["zfill"]))
    if "map" in spec:
        mapping = {to_str(k): to_str(v) for k, v in spec["map"].items()}
        s = s.map(lambda v: mapping.get(v, v))
    if "regex_sub" in spec:
        pat, repl = spec["regex_sub"]
        rx = re.compile(pat)
        s = s.map(lambda v: None if v is None else to_str(rx.sub(repl, v)))
    if "case" in spec:
        fn = {"title": _title, "upper": str.upper, "lower": str.lower}[spec["case"]]
        s = s.map(lambda v: None if v is None else fn(v))
    return s


def _title(v: str) -> str:
    """Title-case that keeps apostrophes/okina inside words lower-case (e.g. "ta'u" -> "Ta'u")."""
    return re.sub(
        r"[A-Za-z]+('[a-z]+)?",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        v,
    )


def apply_filter(
    df: pd.DataFrame, include: dict[str, Any] | None, exclude: dict[str, Any] | None
) -> pd.DataFrame:
    """Keep rows matching every ``include`` condition and none of the ``exclude`` ones.

    Conditions are ``{column: value}`` or ``{column: [values]}`` (compared as normalised strings)
    or ``{column: {gt: number}}``.
    """
    mask = pd.Series(True, index=df.index)
    for cond, keep in ((include or {}, True), (exclude or {}, False)):
        for col, val in cond.items():
            if col not in df.columns:
                raise KeyError(f"filter column {col!r} not in layer")
            if isinstance(val, dict) and "gt" in val:
                hit = pd.to_numeric(df[col], errors="coerce") > val["gt"]
            else:
                vals = {to_str(v) for v in (val if isinstance(val, list) else [val])}
                hit = df[col].map(to_str).isin(vals)
            mask &= hit if keep else ~hit
    return df[mask]
