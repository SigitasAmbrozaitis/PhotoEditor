from __future__ import annotations

from datetime import datetime

import pytest

from photoedit.core.export.naming import MAX_NAME_LENGTH, NameFields, expand, plan_names
from photoedit.models.export import CollisionStatus, NamingSettings

SHOT = datetime(2026, 8, 11, 9, 30, 15)


def _fields(original: str = "DSCF5437", **kw: object) -> NameFields:
    return NameFields(original=original, **kw)  # type: ignore[arg-type]


def test_every_token() -> None:
    fields = _fields(captured_at=SHOT, camera="FUJIFILM X-T3", style="warm-matte", preset="web-full")
    template = "{date}_{time}_{seq:03}_{original}_{style}_{preset}_{camera}_{seq}"
    assert expand(template, fields, 7) == "2026-08-11_093015_007_DSCF5437_warm-matte_web-full_FUJIFILM X-T3_7"


def test_missing_fields() -> None:
    assert (
        expand("{date}_{time}_{style}_{preset}_{camera}", _fields(), 1)
        == "nodate_notime_nostyle_custom_nocamera"
    )


def test_unsafe_expansions_are_made_safe() -> None:
    assert expand("{camera}", _fields(camera='A/B:"C"'), 1) == "A_B__C_"
    assert expand("{original}", _fields(original="con"), 1) == "con_"
    assert expand("{original}", _fields(original="..."), 1) == "export"


def _plan(template: str, originals: list[str], existing: set[str] = frozenset(), policy: str = "suffix"):  # type: ignore[no-untyped-def]
    settings = NamingSettings(template=template, on_collision=policy)
    planned = plan_names(settings, [_fields(o) for o in originals], ".jpg", set(existing))
    return [(p.name, p.collision) for p in planned]


def test_unique_within_the_batch() -> None:
    assert _plan("trip", ["a", "b", "c"]) == [
        ("trip.jpg", CollisionStatus.NEW),
        ("trip_2.jpg", CollisionStatus.RENAMED),
        ("trip_3.jpg", CollisionStatus.RENAMED),
    ]
    assert _plan("{original}", ["A", "a"])[1] == ("a_2.jpg", CollisionStatus.RENAMED)  # case-insensitive


def test_suffix_avoids_existing_files() -> None:
    existing = {"a.jpg", "a_2.jpg"}
    assert _plan("{original}", ["a", "b"], existing) == [
        ("a_3.jpg", CollisionStatus.RENAMED),
        ("b.jpg", CollisionStatus.NEW),
    ]


def test_overwrite_and_skip() -> None:
    assert _plan("{original}", ["a", "b"], {"a.jpg"}, "overwrite") == [
        ("a.jpg", CollisionStatus.OVERWRITE),
        ("b.jpg", CollisionStatus.NEW),
    ]
    assert _plan("{original}", ["a", "b"], {"a.jpg"}, "skip") == [
        ("a.jpg", CollisionStatus.SKIP),
        ("b.jpg", CollisionStatus.NEW),
    ]
    # Batch duplicates still get their own names; a re-export of the same batch is skipped as a whole.
    assert _plan("x", ["a", "b"], {"x.jpg", "x_2.jpg"}, "skip") == [
        ("x.jpg", CollisionStatus.SKIP),
        ("x_2.jpg", CollisionStatus.SKIP),
    ]


@pytest.mark.parametrize("policy", ["suffix", "overwrite", "skip"])
def test_long_names_are_shortened(policy: str) -> None:
    long = "x" * 300
    names = [name for name, _ in _plan("{original}", [long, long], policy=policy)]
    assert all(len(n) <= MAX_NAME_LENGTH and n.endswith(".jpg") for n in names)
    assert names[1].endswith("_2.jpg") and names[0] != names[1]
