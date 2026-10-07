from __future__ import annotations

from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models.export import ColorSpace, ExportTarget, ResizeMode


def _by_id(preset_id: str):  # type: ignore[no-untyped-def]
    return next(p for p in BUILTIN_PRESETS if p.id == preset_id)


def test_ids_unique_and_builtin() -> None:
    ids = [p.id for p in BUILTIN_PRESETS]
    assert len(ids) == len(set(ids))
    assert all(p.builtin for p in BUILTIN_PRESETS)


def test_expected_presets_exist() -> None:
    expected = {
        "instagram-portrait",
        "instagram-square",
        "instagram-landscape",
        "instagram-story",
        "print-4x6",
        "print-5x7",
        "print-8x10",
        "print-a4",
        "print-a3-fine-art",
        "web-full",
    }
    assert {p.id for p in BUILTIN_PRESETS} == expected


def test_instagram_portrait_is_1080x1350_srgb() -> None:
    s = _by_id("instagram-portrait").settings
    assert (s.size.mode, s.size.width, s.size.height) == (ResizeMode.WIDTH_HEIGHT, 1080, 1350)
    assert s.aspect.ratio == "4:5"
    assert s.color_space == ColorSpace.SRGB


def test_instagram_presets_are_srgb_jpeg() -> None:
    for p in BUILTIN_PRESETS:
        if p.target == ExportTarget.INSTAGRAM:
            assert p.settings.color_space == ColorSpace.SRGB
            assert p.settings.file.format == "jpeg"
            assert p.settings.size.width == 1080


def test_size_matches_aspect_ratio() -> None:
    for p in BUILTIN_PRESETS:
        s = p.settings
        if s.size.mode != ResizeMode.WIDTH_HEIGHT or s.aspect.ratio is None:
            continue
        a, b = (float(x) for x in s.aspect.ratio.split(":"))
        assert s.size.width is not None and s.size.height is not None
        size_ratio = max(s.size.width, s.size.height) / min(s.size.width, s.size.height)
        assert abs(size_ratio - max(a, b) / min(a, b)) < 0.01, p.id


def test_print_presets_are_300_ppi() -> None:
    for p in BUILTIN_PRESETS:
        if p.target == ExportTarget.PRINT:
            assert p.settings.size.ppi == 300
