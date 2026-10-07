"""Built-in export presets (read-only; users duplicate them to customize)."""

from __future__ import annotations

from typing import Any

from photoedit.models import ExportPreset


def _preset(id_: str, name: str, target: str, description: str, settings: dict[str, Any]) -> ExportPreset:
    return ExportPreset.model_validate(
        {
            "id": id_,
            "name": name,
            "target": target,
            "description": description,
            "builtin": True,
            "settings": settings,
        }
    )


def _instagram(width: int, height: int, ratio: str) -> dict[str, Any]:
    return {
        "file": {"format": "jpeg", "jpeg_quality": 92},
        "color_space": "srgb",
        "size": {"mode": "width_height", "width": width, "height": height, "dont_enlarge": False, "ppi": 72},
        "aspect": {"ratio": ratio, "orientation": "auto" if ratio == "1:1" else _orientation(width, height)},
        "sharpening": {"target": "screen", "amount": "standard"},
        "metadata": {"policy": "copyright_only", "strip_gps": True},
        "naming": {"template": "{original}_ig"},
    }


def _orientation(width: int, height: int) -> str:
    return "portrait" if height > width else "landscape"


def _print(long_px: int, short_px: int, ratio: str, *, fine_art: bool = False) -> dict[str, Any]:
    file = (
        {"format": "tiff", "bit_depth": 16, "tiff_compression": "lzw"}
        if fine_art
        else {"format": "jpeg", "jpeg_quality": 100}
    )
    return {
        "file": file,
        "color_space": "adobe_rgb" if fine_art else "srgb",
        # width/height are given for portrait; orientation "auto" follows the photo.
        "size": {
            "mode": "width_height",
            "width": short_px,
            "height": long_px,
            "dont_enlarge": False,
            "ppi": 300,
        },
        "aspect": {"ratio": ratio, "orientation": "auto"},
        "sharpening": {"target": "matte_paper" if fine_art else "glossy_paper", "amount": "standard"},
        "metadata": {"policy": "all_except_camera_and_gps", "strip_gps": True},
        "naming": {"template": "{original}_print"},
    }


BUILTIN_PRESETS: tuple[ExportPreset, ...] = (
    _preset(
        "instagram-portrait",
        "Instagram portrait (4:5)",
        "instagram",
        "1080×1350, the largest feed format. Best for most photos.",
        _instagram(1080, 1350, "4:5"),
    ),
    _preset(
        "instagram-square",
        "Instagram square (1:1)",
        "instagram",
        "1080×1080 square feed post.",
        _instagram(1080, 1080, "1:1"),
    ),
    _preset(
        "instagram-landscape",
        "Instagram landscape (1.91:1)",
        "instagram",
        "1080×566 wide feed post. Appears small in the feed; prefer portrait when possible.",
        _instagram(1080, 566, "1.91:1"),
    ),
    _preset(
        "instagram-story",
        "Instagram story / reel (9:16)",
        "instagram",
        "1080×1920 full-screen vertical.",
        _instagram(1080, 1920, "9:16"),
    ),
    _preset(
        "print-4x6",
        "Print 4×6 in (10×15 cm)",
        "print",
        "1800×1200 at 300 PPI. sRGB JPEG, which most photo labs expect.",
        _print(1800, 1200, "3:2"),
    ),
    _preset(
        "print-5x7",
        "Print 5×7 in (13×18 cm)",
        "print",
        "2100×1500 at 300 PPI. sRGB JPEG.",
        _print(2100, 1500, "7:5"),
    ),
    _preset(
        "print-8x10",
        "Print 8×10 in (20×25 cm)",
        "print",
        "3000×2400 at 300 PPI. sRGB JPEG.",
        _print(3000, 2400, "5:4"),
    ),
    _preset(
        "print-a4",
        "Print A4 (21×29.7 cm)",
        "print",
        "3508×2480 at 300 PPI. sRGB JPEG.",
        _print(3508, 2480, "1.414:1"),
    ),
    _preset(
        "print-a3-fine-art",
        "Print A3 fine art (29.7×42 cm)",
        "print",
        "4961×3508 at 300 PPI. 16-bit Adobe RGB TIFF for fine-art printers and matte paper.",
        _print(4961, 3508, "1.414:1", fine_art=True),
    ),
    _preset(
        "web-full",
        "Web full size",
        "web",
        "Long edge 2048 px, sRGB JPEG. For websites, galleries, sharing.",
        {
            "file": {"format": "jpeg", "jpeg_quality": 85},
            "color_space": "srgb",
            "size": {"mode": "long_edge", "long_edge": 2048, "ppi": 72},
            "sharpening": {"target": "screen", "amount": "standard"},
            "metadata": {"policy": "copyright_only", "strip_gps": True},
            "naming": {"template": "{original}_web"},
        },
    ),
)
