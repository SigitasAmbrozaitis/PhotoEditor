"""Export settings (Lightroom export parity, staged — see PLAN.md 4.6)."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class FileFormat(StrEnum):
    JPEG = "jpeg"
    TIFF = "tiff"
    PNG = "png"


class TiffCompression(StrEnum):
    NONE = "none"
    LZW = "lzw"
    ZIP = "zip"


class DecodeSize(StrEnum):
    AUTO = "auto"
    FULL = "full"


class FileSettings(_Section):
    format: FileFormat = FileFormat.JPEG
    jpeg_quality: int = Field(default=90, ge=1, le=100)
    max_file_size_kb: int | None = Field(default=None, ge=50, description="JPEG only: shrink quality to fit.")
    bit_depth: int = Field(default=8, description="8 or 16 (16 only for TIFF/PNG).")
    tiff_compression: TiffCompression = TiffCompression.LZW
    decode: DecodeSize = Field(
        default=DecodeSize.AUTO,
        description="auto = decode a RAW at half size when that still covers the output size; "
        "full = always full size.",
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.bit_depth not in (8, 16):
            raise ValueError("bit_depth must be 8 or 16")
        if self.bit_depth == 16 and self.format == FileFormat.JPEG:
            raise ValueError("JPEG supports 8-bit only")
        if self.max_file_size_kb is not None and self.format != FileFormat.JPEG:
            raise ValueError("max_file_size_kb applies to JPEG only")
        return self


class ColorSpace(StrEnum):
    SRGB = "srgb"
    DISPLAY_P3 = "display_p3"
    ADOBE_RGB = "adobe_rgb"


class ResizeMode(StrEnum):
    ORIGINAL = "original"
    LONG_EDGE = "long_edge"
    SHORT_EDGE = "short_edge"
    WIDTH_HEIGHT = "width_height"
    MEGAPIXELS = "megapixels"
    PERCENTAGE = "percentage"


class SizeSettings(_Section):
    mode: ResizeMode = ResizeMode.ORIGINAL
    long_edge: int | None = Field(default=None, ge=16, le=65535, description="Pixels (mode=long_edge).")
    short_edge: int | None = Field(default=None, ge=16, le=65535, description="Pixels (mode=short_edge).")
    width: int | None = Field(default=None, ge=16, le=65535, description="Pixels (mode=width_height).")
    height: int | None = Field(default=None, ge=16, le=65535, description="Pixels (mode=width_height).")
    megapixels: float | None = Field(default=None, gt=0, le=500)
    percentage: float | None = Field(default=None, gt=0, le=100)
    dont_enlarge: bool = True
    ppi: int = Field(default=300, ge=1, le=2400, description="Print resolution stored in the file.")

    @model_validator(mode="after")
    def _required_value(self) -> Self:
        required: dict[ResizeMode, tuple[str, ...]] = {
            ResizeMode.LONG_EDGE: ("long_edge",),
            ResizeMode.SHORT_EDGE: ("short_edge",),
            ResizeMode.WIDTH_HEIGHT: ("width", "height"),
            ResizeMode.MEGAPIXELS: ("megapixels",),
            ResizeMode.PERCENTAGE: ("percentage",),
        }
        missing = [name for name in required.get(self.mode, ()) if getattr(self, name) is None]
        if missing:
            raise ValueError(f"resize mode '{self.mode}' requires: {', '.join(missing)}")
        return self


class Orientation(StrEnum):
    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class CropAnchor(StrEnum):
    SUBJECT = "subject"
    CENTER = "center"


class AspectSettings(_Section):
    ratio: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?:\d+(\.\d+)?$",
        description="Crop to this aspect ratio, e.g. '4:5'. None = keep the photo's own aspect.",
    )
    orientation: Orientation = Field(
        default=Orientation.AUTO,
        description="auto = follow the photo; otherwise force the ratio's orientation.",
    )
    anchor: CropAnchor = Field(
        default=CropAnchor.CENTER,
        description="What the aspect crop is centered on. 'subject' needs subject detection (Phase 6).",
    )


class SharpenFor(StrEnum):
    NONE = "none"
    SCREEN = "screen"
    MATTE_PAPER = "matte_paper"
    GLOSSY_PAPER = "glossy_paper"


class SharpenAmount(StrEnum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class OutputSharpening(_Section):
    target: SharpenFor = SharpenFor.SCREEN
    amount: SharpenAmount = SharpenAmount.STANDARD


class MetadataPolicy(StrEnum):
    ALL = "all"
    COPYRIGHT_ONLY = "copyright_only"
    COPYRIGHT_AND_CONTACT = "copyright_and_contact"
    ALL_EXCEPT_CAMERA_AND_GPS = "all_except_camera_and_gps"


class MetadataSettings(_Section):
    policy: MetadataPolicy = MetadataPolicy.ALL_EXCEPT_CAMERA_AND_GPS
    strip_gps: bool = Field(
        default=True, description="Only matters for policy 'all'; the others never write GPS."
    )
    copyright: str | None = Field(
        default=None,
        max_length=200,
        description="Copyright notice; {year} = the photo's capture year. None = the configured default.",
    )
    creator: str | None = Field(default=None, max_length=200, description="None = the configured default.")
    keywords: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, keywords: list[str]) -> list[str]:
        for keyword in keywords:
            if not keyword.strip():
                raise ValueError("keywords must not be empty")
            if len(keyword) > 64:
                raise ValueError(f"keyword longer than 64 characters: '{keyword[:20]}…'")
        return keywords

    @model_validator(mode="after")
    def _gps(self) -> Self:
        if not self.strip_gps and self.policy != MetadataPolicy.ALL:
            raise ValueError(
                f"metadata policy '{self.policy}' never writes GPS; keep strip_gps on or use 'all'"
            )
        return self


class CollisionPolicy(StrEnum):
    SUFFIX = "suffix"
    OVERWRITE = "overwrite"
    SKIP = "skip"


NAMING_TOKENS = ("original", "date", "time", "seq", "style", "preset", "camera")
_TOKEN = re.compile(r"\{([^{}]*)\}")
_SEQ_FORMAT = re.compile(r"seq:0([1-9])")
# Characters Windows doesn't allow in file names, and names it reserves for devices.
_FORBIDDEN = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
)

type TemplatePart = str | tuple[str, int]


def parse_template(template: str) -> list[TemplatePart]:
    """Split a naming template into literal text and (token, zero-pad width) pairs.

    Raises ``ValueError`` for unknown tokens, stray braces and characters that can't be in a file name.
    """
    parts: list[TemplatePart] = []
    pos = 0
    for match in _TOKEN.finditer(template):
        parts.append(template[pos : match.start()])
        name = match.group(1)
        if seq := _SEQ_FORMAT.fullmatch(name):
            parts.append(("seq", int(seq.group(1))))
        elif name in NAMING_TOKENS:
            parts.append((name, 0))
        else:
            known = " ".join(f"{{{t}}}" for t in NAMING_TOKENS)
            raise ValueError(f"unknown token {{{name}}} in the name template; known: {known} {{seq:03}}")
        pos = match.end()
    parts.append(template[pos:])
    literals = [p for p in parts if isinstance(p, str)]
    if any("{" in text or "}" in text for text in literals):
        raise ValueError("unmatched brace in the name template")
    bad = sorted({c for text in literals for c in text if c in _FORBIDDEN})
    if bad:
        shown = " ".join(repr(c) for c in bad)
        raise ValueError(f"the name template contains characters not allowed in file names: {shown}")
    if template.endswith((".", " ")):
        raise ValueError("the name template must not end with a dot or a space")
    if len(parts) == 1 and template.strip().lower() in WINDOWS_RESERVED:
        raise ValueError(f"'{template}' is a reserved file name on Windows")
    return [p for p in parts if p != ""]


class NamingSettings(_Section):
    template: str = Field(
        default="{original}",
        min_length=1,
        max_length=200,
        description="Tokens: {original} {date} {time} {seq} {seq:03} {style} {preset} {camera}. "
        "The extension comes from the file format.",
    )
    on_collision: CollisionPolicy = CollisionPolicy.SUFFIX

    @field_validator("template")
    @classmethod
    def _template(cls, template: str) -> str:
        parse_template(template)
        return template


class ExportTarget(StrEnum):
    INSTAGRAM = "instagram"
    PRINT = "print"
    WEB = "web"
    CUSTOM = "custom"


class ExportSettings(_Section):
    """Everything needed to turn an edited photo into an output file."""

    file: FileSettings = Field(default_factory=FileSettings)
    color_space: ColorSpace = ColorSpace.SRGB
    size: SizeSettings = Field(default_factory=SizeSettings)
    aspect: AspectSettings = Field(default_factory=AspectSettings)
    sharpening: OutputSharpening = Field(default_factory=OutputSharpening)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    naming: NamingSettings = Field(default_factory=NamingSettings)
    destination: str | None = Field(default=None, description="Default output folder. None = ask every time.")


class ExportPreset(_Section):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    target: ExportTarget = ExportTarget.CUSTOM
    builtin: bool = Field(default=False, description="Built-in presets can't be edited, only duplicated.")
    settings: ExportSettings = Field(default_factory=ExportSettings)


class CollisionStatus(StrEnum):
    NEW = "new"
    RENAMED = "renamed"
    OVERWRITE = "overwrite"
    SKIP = "skip"


class ExportPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    photo_id: str
    filename: str = Field(description="The original's file name.")
    output_name: str = Field(description="File name in the destination.")
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    decode: DecodeSize = Field(description="How the original is decoded for this export.")
    collision: CollisionStatus
    warnings: list[str] = Field(default_factory=list)


class ExportPlan(BaseModel):
    """What an export would write (a dry run: nothing is written)."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    destination: str = Field(description="The destination folder, absolute.")
    items: list[ExportPlanItem]
    warnings: list[str] = Field(default_factory=list, description="Warnings about the whole export.")
