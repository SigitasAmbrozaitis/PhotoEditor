"""Styles: reusable looks applied to many photos.

A style is sparse: ``values`` holds only the parameters it sets (dotted names), and ``rules`` adapt it to each
photo (adaptive rules, run per photo on numbers measured once per photo). Photos reference a style by id (live
link), so the stored ``Style`` is the single source of a look. See docs/styles.md.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from photoedit.models.adjustments import AdjustmentParams

STYLE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
STYLE_SCHEMA_VERSION = 1
RULE_VERSIONS = {"exposure": 1, "white_balance": 1}

# Parameter groups a style may not set: geometry is per photo, white balance goes through a white_balance rule
# (a fixed Kelvin value would look wrong on photos shot under other light).
STYLE_FORBIDDEN_PREFIXES = {
    "geometry": "geometry (crop, rotation) is per photo, never part of a style",
    "white_balance": "a style sets white balance through a white_balance rule, not as fixed values",
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


# ----------------------------------------------------------------- rules


class ExposureMetering(StrEnum):
    MIDDLE = "middle"
    HIGHLIGHTS = "highlights"
    CAMERA_SETTINGS = "camera_settings"


class WhiteBalanceMode(StrEnum):
    AS_SHOT = "as_shot"
    AUTO = "auto"
    FIXED = "fixed"


class _Rule(_Model):
    rule_version: int = Field(default=1, description="Format version of this rule type.")

    @model_validator(mode="after")
    def _known_version(self) -> Self:
        rule_type: str = type(self).model_fields["type"].default
        supported = RULE_VERSIONS[rule_type]
        if self.rule_version > supported:
            raise ValueError(
                f"rule '{rule_type}' version {self.rule_version} is newer than this tool supports "
                f"({supported})"
            )
        if self.rule_version < 1:
            raise ValueError(f"rule '{rule_type}': rule_version must be at least 1")
        return self


class ExposureRule(_Rule):
    """Auto exposure: moves a measure of the photo toward a target, so differently exposed photos match."""

    type: Literal["exposure"] = "exposure"
    metering: ExposureMetering = Field(
        default=ExposureMetering.MIDDLE,
        description=(
            "What is measured. middle: the median brightness (ordinary scenes). highlights: the white "
            "point, so dark subjects (a black cat, night streets) stay dark. camera_settings: the exposure "
            "dialed in (shutter, aperture, ISO); evens out a series shot in the same light, needs a group "
            "reference."
        ),
    )
    target: float | None = Field(
        default=None,
        ge=-4,
        le=4,
        description="Target in stops relative to mid gray. None = the metering's default (docs/styles.md).",
    )
    use_group: bool = Field(
        default=True, description="Target the photo's group reference when it has one ('even out')."
    )
    strength: float = Field(default=100, ge=0, le=100, description="How far toward the target, in percent.")
    max_change: float = Field(
        default=1.5, ge=0, le=3, description="Largest exposure change in EV either way."
    )


class WhiteBalanceRule(_Rule):
    """White balance relative to each photo, instead of a fixed Kelvin value."""

    type: Literal["white_balance"] = "white_balance"
    mode: WhiteBalanceMode = Field(
        default=WhiteBalanceMode.AS_SHOT,
        description=(
            "as_shot: the camera's white balance plus the offsets. auto: a neutral estimate from the photo "
            "plus the offsets (can remove intentional warm light). fixed: temperature and tint as given."
        ),
    )
    temperature_offset: float = Field(
        default=0,
        ge=-3000,
        le=3000,
        description="Kelvin at 5500 K, applied as the same mired shift (looks alike under any light).",
    )
    tint_offset: float = Field(default=0, ge=-50, le=50, description="Added to the tint.")
    temperature: float | None = Field(
        default=None, ge=2000, le=50000, description="Kelvin (fixed mode only)."
    )
    tint: float | None = Field(default=None, ge=-150, le=150, description="Tint (fixed mode only).")

    @model_validator(mode="after")
    def _mode_fields(self) -> Self:
        if self.mode is WhiteBalanceMode.FIXED:
            if self.temperature is None or self.tint is None:
                raise ValueError("white_balance rule: fixed mode needs temperature and tint")
            if self.temperature_offset or self.tint_offset:
                raise ValueError("white_balance rule: offsets don't apply in fixed mode")
        elif self.temperature is not None or self.tint is not None:
            raise ValueError(
                f"white_balance rule: temperature/tint are only for fixed mode, not '{self.mode}'"
            )
        return self


StyleRule = Annotated[ExposureRule | WhiteBalanceRule, Field(discriminator="type")]
RULE_ORDER = ("exposure", "white_balance")


class RuleResult(_Model):
    """What one rule did on one photo (for display, reports and the AI)."""

    type: str
    summary: str = Field(description="One line, e.g. 'middle -2.1 → target -1.0 stops: +1.1 EV'.")
    measured: float | None = None
    target: float | None = None
    values: dict[str, float] = Field(
        default_factory=dict, description="Parameters the rule set, e.g. {'tone.exposure': 0.6}."
    )
    note: str | None = Field(default=None, description="Why the rule fell back or was limited, if it did.")


# ----------------------------------------------------------------- style


class StyleSample(_Model):
    """A before/after pair rendered from a library photo (files under samples/)."""

    photo_id: str
    caption: str = ""
    name: str = Field(pattern=r"^[a-z0-9-]+$", description="File stem: <name>-before.jpg / <name>-after.jpg.")
    look_hash: str = Field(description="The style's look when the pair was rendered.")


class Style(_Model):
    """A style as stored in ``styles/<id>/style.json``."""

    schema_version: int = Field(default=STYLE_SCHEMA_VERSION, ge=1)
    id: str = Field(pattern=STYLE_ID_PATTERN, description="Slug, also the folder name under styles/.")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    best_for: list[str] = Field(default_factory=list, description="Scenes/subjects the style suits.")
    avoid_on: list[str] = Field(default_factory=list, description="Scenes/subjects the style handles badly.")
    values: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters the style sets, as dotted names, e.g. {'tone.contrast': -10}.",
    )
    rules: list[StyleRule] = Field(default_factory=list, description="Adaptive rules, at most one per type.")
    test_photo_ids: list[str] = Field(
        default_factory=list, description="Hard test cases every change is checked on."
    )
    samples: list[StyleSample] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    version: int = Field(default=1, ge=1, description="Incremented on every saved change.")
    change_note: str = Field(default="", max_length=500, description="What changed in this version.")

    @field_validator("values")
    @classmethod
    def _valid_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        return normalize_values(values)

    @field_validator("rules")
    @classmethod
    def _one_per_type(
        cls, rules: list[ExposureRule | WhiteBalanceRule]
    ) -> list[ExposureRule | WhiteBalanceRule]:
        types = [r.type for r in rules]
        duplicates = sorted({t for t in types if types.count(t) > 1})
        if duplicates:
            raise ValueError(f"at most one rule per type; repeated: {', '.join(duplicates)}")
        return sorted(rules, key=lambda r: RULE_ORDER.index(r.type))

    def rule[R: (ExposureRule, WhiteBalanceRule)](self, kind: type[R]) -> R | None:
        return next((r for r in self.rules if isinstance(r, kind)), None)

    def look_hash(self) -> str:
        """Identifies the look (values + rules); text, test set and timestamps don't change it."""
        look = {"values": self.values, "rules": [r.model_dump(mode="json") for r in self.rules]}
        canonical = json.dumps(look, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def normalize_values(values: dict[str, Any]) -> dict[str, Any]:
    """Check a style's dotted values and return them sorted, in the parameters' own JSON form (so ``-10`` and
    ``-10.0`` hash alike). Raises ``ValueError`` with the offending name."""
    for name in values:
        group = name.split(".", 1)[0]
        if group in STYLE_FORBIDDEN_PREFIXES:
            raise ValueError(f"'{name}': {STYLE_FORBIDDEN_PREFIXES[group]}")
    try:
        applied = AdjustmentParams().with_values(values)
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(p) for p in error["loc"])
        raise ValueError(f"invalid value at {where}: {error['msg']}") from None
    return applied.dotted(sorted(values))


class StyleSummary(_Model):
    id: str
    name: str
    description: str = ""
    cover_url: str | None = Field(default=None, description="The first sample's 'after' image, if any.")
    updated_at: datetime | None = None
    version: int = Field(default=1, ge=1)
    photo_count: int = Field(default=0, ge=0, description="Photos that use this style.")
    error: str | None = Field(default=None, description="Why the style file can't be used, if it can't.")


class StyleSampleView(_Model):
    photo_id: str
    caption: str
    before_url: str
    after_url: str
    stale: bool = Field(description="Rendered with an older look of the style.")


class StyleView(_Model):
    """API response for a style: the stored style plus derived, read-only information."""

    id: str
    name: str
    description: str
    best_for: list[str]
    avoid_on: list[str]
    values: dict[str, Any]
    rules: list[StyleRule]
    test_photo_ids: list[str]
    samples: list[StyleSampleView]
    created_at: datetime
    updated_at: datetime
    version: int
    change_note: str
    look_hash: str
    changed_parameters: dict[str, Any] = Field(description="Same as values (what the style changes).")
    cover_url: str | None = None
    photo_count: int = Field(ge=0)
    samples_stale: bool = Field(description="Some samples show an older look of the style.")


def sample_url(style_id: str, sample: StyleSample, which: Literal["before", "after"]) -> str:
    return f"/api/styles/{style_id}/samples/{sample.name}/{which}.jpg?v={sample.look_hash}"


def style_view(style: Style, *, photo_count: int = 0) -> StyleView:
    look = style.look_hash()
    samples = [
        StyleSampleView(
            photo_id=s.photo_id,
            caption=s.caption,
            before_url=sample_url(style.id, s, "before"),
            after_url=sample_url(style.id, s, "after"),
            stale=s.look_hash != look,
        )
        for s in style.samples
    ]
    return StyleView(
        id=style.id,
        name=style.name,
        description=style.description,
        best_for=style.best_for,
        avoid_on=style.avoid_on,
        values=style.values,
        rules=style.rules,
        test_photo_ids=style.test_photo_ids,
        samples=samples,
        created_at=style.created_at,
        updated_at=style.updated_at,
        version=style.version,
        change_note=style.change_note,
        look_hash=look,
        changed_parameters=style.values,
        cover_url=samples[0].after_url if samples else None,
        photo_count=photo_count,
        samples_stale=any(s.stale for s in samples),
    )


def style_summary(style: Style, *, photo_count: int = 0) -> StyleSummary:
    view = style_view(style, photo_count=photo_count)
    return StyleSummary(
        id=style.id,
        name=style.name,
        description=style.description,
        cover_url=view.cover_url,
        updated_at=style.updated_at,
        version=style.version,
        photo_count=photo_count,
    )


# ----------------------------------------------------------------- consistency report


class PhotoMeasurements(_Model):
    """Measurements of one render: brightness in stops relative to mid gray, white balance in Kelvin/tint."""

    middle: float | None = Field(default=None, description="Median brightness.")
    white: float | None = Field(default=None, description="White point (99.5th percentile).")
    temperature: float | None = None
    tint: float | None = None


class ReportPhoto(_Model):
    photo_id: str
    filename: str
    camera_ev: float | None = Field(default=None, description="Exposure dialed in (EV100) from EXIF.")
    before: PhotoMeasurements
    after: PhotoMeasurements
    rules: list[RuleResult] = Field(default_factory=list)
    deviation: float = Field(description="Distance of 'after' middle from the set's median, in stops.")


class Spread(_Model):
    """How far apart one measurement is across the set (smaller = more consistent)."""

    measure: str
    before_mad: float = Field(description="Median absolute deviation before the style.")
    after_mad: float
    before_range: float = Field(description="Largest minus smallest before the style.")
    after_range: float


class ConsistencyReport(_Model):
    style_id: str | None
    look_hash: str | None
    photos: list[ReportPhoto]
    spread: list[Spread]
