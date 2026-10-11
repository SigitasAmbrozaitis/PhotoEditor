from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models import ExportPlan, ExportPlanItem, ExportSettings
from photoedit.models.export import (
    AspectSettings,
    CropAnchor,
    DecodeSize,
    FileSettings,
    MetadataSettings,
    NamingSettings,
    parse_template,
)


def test_defaults() -> None:
    assert FileSettings().decode == DecodeSize.AUTO
    assert AspectSettings().anchor == CropAnchor.CENTER


def test_parse_template() -> None:
    assert parse_template("{original}") == [("original", 0)]
    assert parse_template("{date}_{seq:03} trip") == [("date", 0), "_", ("seq", 3), " trip"]
    assert parse_template("{seq}{camera}{style}{preset}{time}") == [
        ("seq", 0),
        ("camera", 0),
        ("style", 0),
        ("preset", 0),
        ("time", 0),
    ]


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{nope}", "unknown token {nope}"),
        ("{seq:3}", "unknown token {seq:3}"),
        ("{original", "unmatched brace"),
        ("a}b", "unmatched brace"),
        ("a/b", "not allowed in file names: '/'"),
        ("x:{original}?", "':' '?'"),
        ("{original}.", "must not end with a dot"),
        ("{original} ", "must not end with a dot or a space"),
        ("CON", "reserved file name"),
        ("lpt1", "reserved file name"),
    ],
)
def test_template_rejected(template: str, message: str) -> None:
    with pytest.raises(ValidationError, match=re.escape(message)):
        NamingSettings(template=template)


def test_reserved_name_with_tokens_is_fine() -> None:
    NamingSettings(template="con_{original}")


def test_keywords_validated() -> None:
    MetadataSettings(keywords=["rally", "cat"])
    with pytest.raises(ValidationError, match="must not be empty"):
        MetadataSettings(keywords=[" "])
    with pytest.raises(ValidationError, match="longer than 64"):
        MetadataSettings(keywords=["x" * 65])
    with pytest.raises(ValidationError, match="at most 50"):
        MetadataSettings(keywords=[f"k{i}" for i in range(51)])


def test_strip_gps_only_matters_for_all() -> None:
    MetadataSettings(policy="all", strip_gps=False)
    with pytest.raises(ValidationError, match="never writes GPS"):
        MetadataSettings(policy="copyright_only", strip_gps=False)


def test_export_plan_round_trip() -> None:
    plan = ExportPlan(
        destination="C:/out",
        items=[
            ExportPlanItem(
                photo_id="p1",
                filename="a.RAF",
                output_name="a.jpg",
                width=1080,
                height=1350,
                decode="half",
                collision="new",
                warnings=["enlarged 1.4×"],
            )
        ],
    )
    assert ExportPlan.model_validate_json(plan.model_dump_json()) == plan


def test_builtin_presets_center_and_print_full_decode() -> None:
    for preset in BUILTIN_PRESETS:
        assert preset.settings.aspect.anchor == CropAnchor.CENTER
        expected = DecodeSize.FULL if preset.target == "print" else DecodeSize.AUTO
        assert preset.settings.file.decode == expected, preset.id
        ExportSettings.model_validate_json(preset.settings.model_dump_json())
