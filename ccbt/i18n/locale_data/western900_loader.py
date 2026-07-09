"""Aggregate hand-written Western (es/eu/fr) overlays for 1400 prioritized POT msgids."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

Quad = tuple[str, str, str, str]


def iter_western900_quads() -> Iterator[Quad]:
    """Yield ``(msgid, es, eu, fr)`` in stable order (1400 rows)."""
    from ccbt.i18n.locale_data import (
        western900_ts_01,
        western900_ts_02,
        western900_ts_03,
        western900_ts_04,
        western900_ts_05,
        western900_ts_06,
        western900_ts_07,
        western900_ts_08,
        western900_ts_09,
        western900_ts_10,
        western900_ts_11,
        western900_ts_12,
        western900_ts_13,
        western900_ts_14,
        western900_ts_15,
    )

    for mod in (
        western900_ts_01,
        western900_ts_02,
        western900_ts_03,
        western900_ts_04,
        western900_ts_05,
        western900_ts_06,
        western900_ts_07,
        western900_ts_08,
        western900_ts_09,
        western900_ts_10,
        western900_ts_11,
        western900_ts_12,
        western900_ts_13,
        western900_ts_14,
        western900_ts_15,
    ):
        yield from mod.ROWS


def split_es_eu_fr() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return three ``msgid -> msgstr`` maps for Spanish, Basque, and French."""
    es: dict[str, str] = {}
    eu: dict[str, str] = {}
    fr: dict[str, str] = {}
    for m, s, e, f in iter_western900_quads():
        es[m] = s
        eu[m] = e
        fr[m] = f
    return es, eu, fr
