"""Load and validate the configuration: countries.yml, levels.yml and sources/<ISO3>.yml.

The register schema is checked with jsonschema (structure) plus Python checks for the
processing keys of every level entry that will actually be processed (see :func:`used_levels`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import jsonschema
import yaml

from pab import io as pio

logger = logging.getLogger(__name__)

LEVEL_RANK = {
    "eez": 0,
    "admin0": 1,
    "admin1": 2,
    "admin2": 3,
    "admin3": 4,
    "admin4": 5,
    "admin5": 6,
    "other": 99,
}
ADMIN_CODES = ["admin0", "admin1", "admin2", "admin3", "admin4", "admin5"]

_FIELD_SPEC = {
    "oneOf": [
        {"type": "null"},
        {"type": "string"},
        {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "template": {"type": "string"},
                "value": {"type": ["string", "number"]},
                "floordiv": {"type": "integer", "minimum": 1},
                "slice": {
                    "type": "array",
                    "items": {"type": ["integer", "null"]},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "map": {"type": "object"},
                "regex_sub": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "case": {"enum": ["title", "upper", "lower"]},
                "zfill": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ]
}

LEVEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["level_code", "level_type", "nests"],
    "properties": {
        "level_code": {"enum": list(LEVEL_RANK)},
        "level_type": {"type": "string"},
        "level_name_local": {"type": ["string", "null"]},
        "layer": {"type": ["string", "null"]},
        "name_field": _FIELD_SPEC,
        "name_alt_field": _FIELD_SPEC,
        "code_field": _FIELD_SPEC,
        "parent_field": _FIELD_SPEC,
        "code_scheme": {"type": "string"},
        "nests": {"type": "boolean"},
        "use": {"type": "boolean"},
        "filter": {"type": "object"},
        "exclude": {"type": "object"},
        "dissolve": {"type": "boolean"},
        "name_map": {"type": "object"},
        "parent_candidate": {"type": "boolean"},
        "split_by_parent": {"type": "boolean"},
        "nest_check": {"type": "object"},
        "layer_key": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "license": {"type": "object", "required": ["name"]},
        "derive": {"type": "object"},
        "clip_to": {
            "type": "object",
            "required": ["source_id", "layer"],
            "properties": {
                "source_id": {"type": "string"},
                "layer": {"type": "string"},
                "filter": {"type": "object"},
                "exclude": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "notes": {"type": ["string", "null"]},
    },
}

REGISTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["iso3", "sources"],
    "properties": {
        "iso3": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "country_name": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_id", "status", "license", "levels"],
                "properties": {
                    "source_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                    "status": {
                        "enum": ["selected", "alternative", "rejected", "reference"]
                    },
                    "license": {"type": "object", "required": ["name"]},
                    "levels": {"type": ["array", "null"], "items": LEVEL_SCHEMA},
                    "raw_path": {"type": ["string", "null"]},
                    "land_mask": {"type": "object"},
                    "auth": {
                        "type": "object",
                        "required": ["type", "value_env"],
                        "properties": {
                            "type": {"enum": ["header"]},
                            "name": {"type": "string"},
                            "value_env": {
                                "type": "string",
                                "pattern": "^[A-Z_][A-Z0-9_]*$",
                            },
                            "prefix": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        },
        "decisions": {"type": ["array", "null"]},
    },
}


@cache
def countries() -> dict[str, dict[str, Any]]:
    """Country registry keyed by ISO3."""
    doc = yaml.safe_load(pio.read_bytes("config/countries.yml"))
    return {c["iso3"]: c for c in doc["countries"]}


@cache
def level_types() -> dict[str, Any]:
    """Harmonised ``level_type`` vocabulary."""
    return yaml.safe_load(pio.read_bytes("config/levels.yml"))["level_types"]


def load_register(iso3: str) -> dict[str, Any]:
    """Load and schema-validate ``config/sources/<ISO3>.yml``."""
    doc = yaml.safe_load(pio.read_bytes(f"config/sources/{iso3}.yml"))
    validate_register(doc)
    if doc["iso3"] != iso3:
        raise ValueError(f"register iso3 {doc['iso3']} does not match file name {iso3}")
    return doc


def validate_register(doc: dict[str, Any]) -> None:
    """Raise ``jsonschema.ValidationError`` / ``ValueError`` if a register is malformed."""
    jsonschema.validate(doc, REGISTER_SCHEMA)
    ids = [s["source_id"] for s in doc["sources"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate source_id(s): {sorted(dupes)}")
    vocab = level_types()
    for spec in used_levels(doc):
        lvl = spec.level
        if lvl["level_type"] not in vocab:
            raise ValueError(
                f"{spec.source_id}: unknown level_type {lvl['level_type']!r}"
            )
        if not lvl.get("layer") and not lvl.get("derive"):
            raise ValueError(
                f"{spec.source_id} {lvl['level_code']}: needs `layer` or `derive`"
            )
        from pab import licenses

        licenses.check(spec.source, lvl)  # composite/unknown licence, missing agreement
        if spec.source.get("raw_path") is None:
            raise ValueError(f"{spec.source_id}: processed source has no raw_path")


@dataclass
class LevelSpec:
    """One level entry of one source that the processing stage will build."""

    source: dict[str, Any]
    level: dict[str, Any]
    index: int
    notes: list[str] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        """Source id of the owning source."""
        return self.source["source_id"]

    @property
    def level_code(self) -> str:
        """Harmonised level code."""
        return self.level["level_code"]

    @property
    def rank(self) -> int:
        """Harmonised level rank."""
        return LEVEL_RANK[self.level_code]

    @property
    def key(self) -> str:
        """Stable identifier for this level entry (used for ``other`` uids and logs)."""
        if self.level.get("layer_key"):
            return self.level["layer_key"]
        return slug(self.level.get("level_name_local") or self.level["level_type"])

    @property
    def restricted(self) -> bool:
        """True when the source may not be redistributed (``redistribution_ok`` false or unknown)."""
        return self.source["license"].get("redistribution_ok") is not True


def slug(text: str) -> str:
    """Lower-case ASCII slug (letters, digits, single hyphens)."""
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def used_levels(doc: dict[str, Any]) -> list[LevelSpec]:
    """Level entries to process, applying the register's status and decisions.

    * ``use: false`` on a level entry always skips it.
    * Entries of ``selected`` sources are used unless the ``decisions`` block names a different
      source for that ``level_code``.
    * Entries of non-selected sources are used only if a decision names that source for the
      level (register inconsistency, logged) or the entry says ``use: true`` (e.g. open derived
      layers required by an orchestrator ruling).
    """
    chosen: dict[str, set[str]] = {}
    for d in doc.get("decisions") or []:
        chosen.setdefault(d["level_code"], set()).add(d["chosen"])
    out: list[LevelSpec] = []
    for src in doc["sources"]:
        for i, lvl in enumerate(src.get("levels") or []):
            use = lvl.get("use")
            if use is False:
                continue
            code = lvl["level_code"]
            named = chosen.get(code)
            if use is True:
                out.append(LevelSpec(src, lvl, i))
            elif src["status"] == "selected":
                if named and src["source_id"] not in named:
                    continue
                out.append(LevelSpec(src, lvl, i))
            elif named and src["source_id"] in named:
                spec = LevelSpec(src, lvl, i)
                spec.notes.append(
                    f"source status is {src['status']!r} but decisions choose it for {code}; processed"
                )
                out.append(spec)
    return out


def sources_used(iso3_or_register: str | dict[str, Any]) -> list[str]:
    """Every source the processing stage reads for a country, in register order.

    Derived from :func:`used_levels` (selected sources, sources chosen in ``decisions``, and
    level entries with ``use: true``) plus sources referenced inside ``derive`` blocks (e.g.
    supplementary layers for ``islands_from_parts``). ``pab cache`` and ``pab process`` both
    use this list, so the raw cache holds exactly what processing needs.
    """
    doc = (
        load_register(iso3_or_register)
        if isinstance(iso3_or_register, str)
        else iso3_or_register
    )
    ids: list[str] = []
    for spec in used_levels(doc):
        refs = [spec.source_id] + [
            s["source_id"] for s in (spec.level.get("derive") or {}).get("sources", [])
        ]
        if spec.level.get("clip_to"):
            refs.append(spec.level["clip_to"]["source_id"])
        ids.extend(r for r in refs if r not in ids)
    if (
        doc["iso3"] == "EEZ"
    ):  # polygons may come from several sources (eez_polygons.csv)
        from pab import eez

        ids.extend(
            i for i in dict.fromkeys(eez.selection(doc)["source_id"]) if i not in ids
        )
    known = {s["source_id"] for s in doc["sources"]}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise ValueError(
            f"derive/clip_to blocks reference unknown source_id(s): {unknown}"
        )
    order = [s["source_id"] for s in doc["sources"]]
    return sorted(ids, key=order.index)


def country_meta(iso3: str) -> dict[str, Any]:
    """Country registry entry (raises KeyError if unknown)."""
    return countries()[iso3]


def all_iso3() -> list[str]:
    """All country codes in the registry, sorted."""
    return sorted(countries())
