"""Export settings (Lightroom export parity, staged — see PLAN.md 4.6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FileFormat(StrEnum):
    JPEG = "jpeg"
    TIFF = "tiff"
    PNG = "png"


class TiffCompression(StrEnum):
    NONE = "none"
    LZW = "lzw"
    ZIP = "zip"


class FileSettings(_Section):
    format: FileFormat = FileFormat.JPEG
    jpeg_quality: int = Field(default=90, ge=1, le=100)
    max_file_size_kb: int | None = Field(default=None, ge=50, description="JPEG only: shrink quality to fit.")
    bit_depth: int = Field(default=8, description="8 or 16 (16 only for TIFF/PNG).")
    tiff_compression: TiffCompression = TiffCompression.LZW

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
    anchor: CropAnchor = Field(default=CropAnchor.SUBJECT, description="What the aspect crop is centered on.")


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
    strip_gps: bool = True
    copyright: str | None = Field(default=None, max_length=200)
    keywords: list[str] = Field(default_factory=list)


class CollisionPolicy(StrEnum):
    SUFFIX = "suffix"
    OVERWRITE = "overwrite"
    SKIP = "skip"


class NamingSettings(_Section):
    template: str = Field(
        default="{original}",
        min_length=1,
        max_length=200,
        description="Tokens: {original} {date} {time} {seq} {seq:03} {style} {preset}.",
    )
    on_collision: CollisionPolicy = CollisionPolicy.SUFFIX


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
