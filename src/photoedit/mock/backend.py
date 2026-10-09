"""Mock parts of the backend that later phases replace: styles (Phase 4), export (Phase 5).

Styles and their sample images are fake. Apply/export jobs run on the real job manager with the real photos,
but each item only sleeps instead of rendering. Nothing here reads photos or writes files.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.mock import images
from photoedit.models import (
    AdjustmentParams,
    ApplyAndExportRequest,
    ApplyStyleRequest,
    ExportPreset,
    ExportRequest,
    Job,
    JobKind,
    Photo,
    Style,
    StyleSample,
    StyleSummary,
    WhiteBalanceMode,
    WhiteBalanceRule,
    style_summary,
)

SECONDS_PER_ITEM = 0.4  # fake processing time per photo in a job
_BASE_TIME = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)

type PhotoLookup = Callable[[str], Photo]


# ----------------------------------------------------------------- fake styles


def _adjust(**groups: dict[str, object]) -> AdjustmentParams:
    return AdjustmentParams.model_validate(groups)


_STYLE_DEFS: tuple[tuple[str, str, str, list[str], list[str], AdjustmentParams, images.Look], ...] = (
    (
        "warm-film",
        "Warm Film",
        "Soft, warm analog look with gentle contrast, lifted blacks and golden highlights. "
        "Inspired by Portra-style color negative film.",
        ["portraits", "golden hour", "travel"],
        ["night scenes", "cold winter scenes"],
        _adjust(
            white_balance={"temperature": 6200, "tint": 8},
            tone={"exposure": 0.15, "contrast": -12, "highlights": -30, "shadows": 20, "blacks": 15},
            presence={"vibrance": 10, "saturation": -8},
            color_grading={
                "shadows": {"hue": 200, "saturation": 8},
                "highlights": {"hue": 40, "saturation": 15},
            },
            effects={"grain": {"amount": 20}},
        ),
        images.Look(tint=(255, 170, 90), tint_strength=0.12, saturation=0.95, contrast=0.92, brightness=1.05),
    ),
    (
        "moody-forest",
        "Moody Forest",
        "Dark, desaturated greens and teal shadows with deep contrast. "
        "For forests, fog and overcast landscapes.",
        ["forests", "fog", "overcast landscapes"],
        ["portraits with skin tones", "beach"],
        _adjust(
            tone={"exposure": -0.4, "contrast": 25, "highlights": -40, "shadows": -10, "blacks": -15},
            presence={"vibrance": -15, "saturation": -20},
            hsl={"green": {"hue": 20, "saturation": -35, "luminance": -20}, "yellow": {"saturation": -25}},
            color_grading={"shadows": {"hue": 190, "saturation": 20}},
            effects={"vignette": {"amount": -25}},
        ),
        images.Look(tint=(40, 90, 85), tint_strength=0.18, saturation=0.7, contrast=1.25, brightness=0.85),
    ),
    (
        "clean-bright",
        "Clean & Bright",
        "Airy, bright and neutral. Lifted exposure, clean whites and accurate colors.",
        ["interiors", "product", "daylight portraits"],
        ["low-key scenes"],
        _adjust(
            tone={"exposure": 0.5, "contrast": -5, "highlights": -20, "shadows": 30, "whites": 15},
            presence={"vibrance": 15},
        ),
        images.Look(saturation=1.05, contrast=0.95, brightness=1.18),
    ),
    (
        "bw-classic",
        "Classic B&W",
        "Punchy black and white with strong contrast and deep blacks.",
        ["street", "architecture", "dramatic skies"],
        ["scenes that rely on color"],
        _adjust(
            tone={"contrast": 35, "highlights": -15, "shadows": 10, "whites": 20, "blacks": -25},
            presence={"saturation": -100},
            effects={"grain": {"amount": 30}},
        ),
        images.Look(saturation=0.0, contrast=1.35),
    ),
)


def _build_styles() -> dict[str, Style]:
    styles: dict[str, Style] = {}
    for idx, (sid, name, desc, best, avoid, adjustments, _look) in enumerate(_STYLE_DEFS):
        changed = adjustments.changed_fields()
        wb = {k.split(".")[1]: v for k, v in changed.items() if k.startswith("white_balance.")}
        values = {k: v for k, v in changed.items() if not k.startswith(("white_balance.", "effects.grain"))}
        rules = [WhiteBalanceRule(mode=WhiteBalanceMode.FIXED, **wb)] if wb else []
        style = Style(
            id=sid,
            name=name,
            description=desc,
            best_for=best,
            avoid_on=avoid,
            values=values,
            rules=rules,
            created_at=_BASE_TIME - timedelta(days=30 - idx * 5),
            updated_at=_BASE_TIME - timedelta(days=28 - idx * 5),
            version=idx + 1,
        )
        look = style.look_hash()
        samples = [
            StyleSample(photo_id=f"mock-{n}", caption=f"Sample {n + 1}", name=str(n), look_hash=look)
            for n in range(3)
        ]
        styles[sid] = style.model_copy(update={"samples": samples})
    return styles


_LOOKS: dict[str, images.Look] = {d[0]: d[6] for d in _STYLE_DEFS}


# ----------------------------------------------------------------- backend


class MockBackend:
    """Fake styles, the built-in export presets, and simulated apply/export jobs."""

    def __init__(
        self,
        jobs: JobManager,
        photos: PhotoLookup,
        *,
        seconds_per_item: float = SECONDS_PER_ITEM,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._jobs = jobs
        self._photos = photos
        self._seconds_per_item = seconds_per_item
        self._sleep = sleep
        self._styles = _build_styles()
        self._presets: dict[str, ExportPreset] = {p.id: p for p in BUILTIN_PRESETS}

    # ---- styles

    def list_styles(self) -> list[StyleSummary]:
        return [style_summary(s) for s in sorted(self._styles.values(), key=lambda s: s.name)]

    def style(self, style_id: str) -> Style:
        try:
            return self._styles[style_id]
        except KeyError:
            raise NotFoundError(f"style '{style_id}' not found") from None

    def style_sample_image(self, style_id: str, name: str, *, before: bool) -> bytes:
        style = self.style(style_id)
        n = next((i for i, s in enumerate(style.samples) if s.name == name), None)
        if n is None:
            raise NotFoundError(f"style '{style_id}' has no sample '{name}'")
        scene = (list(self._styles).index(style_id) * 3 + n) % len(images.SCENES)
        look = images.FLAT_LOOK if before else _LOOKS[style_id]
        return images.render_placeholder(scene, 800, 533, f"{style.name} #{n + 1}", look)

    # ---- export presets

    def list_presets(self) -> list[ExportPreset]:
        return list(self._presets.values())

    def preset(self, preset_id: str) -> ExportPreset:
        try:
            return self._presets[preset_id]
        except KeyError:
            raise NotFoundError(f"export preset '{preset_id}' not found") from None

    # ---- simulated jobs

    def create_job(self, request: ApplyStyleRequest | ExportRequest | ApplyAndExportRequest) -> Job:
        photos = [self._photos(pid) for pid in request.photo_ids]
        style_id = getattr(request, "style_id", None)
        preset_id = getattr(request, "preset_id", None)
        destination = getattr(request, "destination", None)
        style_name = self.style(style_id).name if style_id else "no style"
        preset_name = self.preset(preset_id).name if preset_id else "custom settings"
        n = len(photos)
        noun = "photo" if n == 1 else "photos"
        titles = {
            JobKind.APPLY_STYLE: f"Apply {style_name} to {n} {noun}",
            JobKind.EXPORT: f"Export {n} {noun} ({preset_name})",
            JobKind.APPLY_AND_EXPORT: f"Apply {style_name} and export {n} {noun} ({preset_name})",
        }
        writes_files = request.kind is not JobKind.APPLY_STYLE

        def work(index: int) -> ItemResult:
            self._sleep(self._seconds_per_item)
            if not writes_files or destination is None:
                return ItemResult()
            stem = photos[index].filename.rsplit(".", 1)[0]
            return ItemResult(output_path=f"{destination.rstrip('/')}/{stem}.jpg", message="simulated")

        return self._jobs.submit(
            request.kind,
            titles[request.kind] + " (simulated)",
            [ItemSpec(filename=p.filename, photo_id=p.id) for p in photos],
            work,
            style_id=style_id,
            preset_id=preset_id,
            destination=destination,
        )
