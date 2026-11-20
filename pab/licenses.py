"""Licence normalisation (ruling D-016).

Every row carries exactly one licence value, resolved for the level the row came from
(a level entry may override its source's licence with ``license: {name, url}``), normalised
to an SPDX id where one exists, plus a ``license_url``. Composite or unknown licence strings
raise an error so they are fixed in the register rather than published.

Agreement-covered sources (decisions D-019/D-020): a register licence may carry
``agreement: "<text>"`` naming a data-use agreement that lets this project redistribute a
source whose public licence would not (e.g. SPC data under CC BY-NC-SA 4.0). The row keeps the
public licence (``license = CC-BY-NC-SA-4.0``) and records the agreement in
``license_agreement``; such sources must set ``redistribution_ok: true``. Downstream users
remain bound by the public licence unless they hold their own agreement.
"""

from __future__ import annotations

import re
from typing import Any

#: canonical value -> canonical URL (None: use the register's URL)
CANONICAL: dict[str, str | None] = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-3.0-IGO": "https://creativecommons.org/licenses/by/3.0/igo/",
    "CC-BY-SA-3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "ODbL-1.0": "https://opendatacommons.org/licenses/odbl/1-0/",
    "LO-2.0": "https://www.etalab.gouv.fr/licence-ouverte-open-licence",
    "CC-BY-NC-SA-4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "Public domain (US Government work)": None,
    "Public domain (Natural Earth)": "https://www.naturalearthdata.com/about/terms-of-use/",
    "Public domain": None,
    "PacIOOS data use (free redistribution, not for legal use)": None,
    "GADM licence": "https://gadm.org/license.html",
    "unspecified": None,
}

# (pattern on the register licence name, canonical value); first match wins
_RULES: list[tuple[str, str]] = [
    (r"^CC-BY-4\.0$", "CC-BY-4.0"),
    # Pacific Data Hub "Creative Commons Attribution" without a version: treated as 4.0, as the
    # retrieval stage did for every other PDH set
    (
        r"^CC-BY( \(.*version unstated.*\)| \(Creative Commons Attribution.*\))?$",
        "CC-BY-4.0",
    ),
    (r"^CC-BY-3\.0-IGO$|^CC-BY-IGO-3\.0$", "CC-BY-3.0-IGO"),
    (r"^CC-BY-SA-3\.0$", "CC-BY-SA-3.0"),
    (r"^ODbL(-1\.0)?$", "ODbL-1.0"),
    (r"^CC-BY-NC-SA-4\.0$", "CC-BY-NC-SA-4.0"),
    (r"^Licence Ouverte( v)?2\.0", "LO-2.0"),
    (r"^Public domain \(US Government work", "Public domain (US Government work)"),
    (r"^Public domain \(Natural Earth\)$", "Public domain (Natural Earth)"),
    (r"^Public [Dd]omain$", "Public domain"),
    (r"^PacIOOS data use", "PacIOOS data use (free redistribution, not for legal use)"),
    (r"^GADM licence", "GADM licence"),
    (r"^unspecified$", "unspecified"),
]


def normalize(name: str) -> str:
    """Map a register licence name to its canonical single value (raises on composites)."""
    for pat, canon in _RULES:
        if re.search(pat, name.strip()):
            return canon
    raise ValueError(
        f"licence {name!r} is composite or unknown: add a per-level `license` override"
    )


#: public licences that do not by themselves allow this project to republish (non-commercial,
#: no-derivatives or unknown terms): a source under one of these with
#: ``redistribution_ok: true`` must name the ``agreement`` that allows it
NEEDS_AGREEMENT = {"CC-BY-NC-SA-4.0", "GADM licence", "unspecified"}


def _licence(source: dict[str, Any], level: dict[str, Any] | None) -> dict[str, Any]:
    return (level or {}).get("license") or source["license"]


def resolve(
    source: dict[str, Any], level: dict[str, Any] | None = None
) -> tuple[str, str | None]:
    """(license, license_url) for a row from ``source`` built by register level entry ``level``."""
    lic = _licence(source, level)
    value = normalize(lic["name"])
    return value, CANONICAL.get(value) or lic.get("url")


def agreement(
    source: dict[str, Any], level: dict[str, Any] | None = None
) -> str | None:
    """Data-use agreement text covering a row (``license.agreement``), else None.

    A level ``license`` override inherits its source's agreement unless it sets its own.
    """
    lic = _licence(source, level)
    text = str(lic.get("agreement") or source["license"].get("agreement") or "").strip()
    return text or None


def redistributable(source: dict[str, Any]) -> bool:
    """True when the source's rows may be republished (``redistribution_ok: true``)."""
    return source["license"].get("redistribution_ok") is True


def check(source: dict[str, Any], level: dict[str, Any] | None = None) -> None:
    """Raise if a licence is unknown, or is non-open and redistributable without an agreement."""
    value, _ = resolve(source, level)
    if (
        value in NEEDS_AGREEMENT
        and redistributable(source)
        and not agreement(source, level)
    ):
        raise ValueError(
            f"{source.get('source_id')}: licence {value} with redistribution_ok true needs "
            "`license.agreement` naming the agreement that allows redistribution"
        )
