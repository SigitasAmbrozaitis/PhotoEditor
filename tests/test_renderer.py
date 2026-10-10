from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.core import renderer as renderer_module
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import EditStore
from photoedit.core.render.anchors import PhotoStats, ToneAnchors
from photoedit.core.render.profile import GENERIC, builtin_profiles
from photoedit.core.renderer import Renderer, profile_of
from photoedit.core.scan import SourceKind
from photoedit.models import AdjustmentParams
from photoedit.safety import PathGuard


def catalog_photo(path: Path, kind: SourceKind = SourceKind.RASTER, **fields: object) -> CatalogPhoto:
    data: dict[str, object] = {
        "id": "pid1",
        "sha256": "e" * 64,
        "path": path,
        "kind": kind,
        "file_size": 1,
        "mtime_ns": 1,
        "width": 320,
        "height": 200,
    }
    data.update(fields)
    return CatalogPhoto.model_validate(data)


@pytest.fixture
def env(tmp_path: Path) -> tuple[Renderer, EditStore, CatalogPhoto]:
    workspace = tmp_path / "workspace"
    guard = PathGuard(writable_roots=[workspace])
    photo = catalog_photo(write_jpeg(tmp_path / "photos" / "a.jpg", (200, 120, 60)))
    return Renderer(workspace / "cache", guard), EditStore(workspace / "edits", guard), photo


def size_of(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_profile_choice(tmp_path: Path) -> None:
    assert profile_of(catalog_photo(tmp_path / "a.jpg")) is None  # JPEG originals are already rendered
    assert profile_of(catalog_photo(tmp_path / "a.RAF", SourceKind.RAW, camera="Some Camera")) is GENERIC
    xt3 = next(p for p in builtin_profiles() if p.model == "X-T3")
    raf = catalog_photo(tmp_path / "a.RAF", SourceKind.RAW, camera="FUJIFILM X-T3", dynamic_range=100)
    assert profile_of(raf) == xt3
    dr400 = profile_of(raf.model_copy(update={"dynamic_range": 400}))
    assert dr400 is not None and dr400.baseline_exposure == pytest.approx(xt3.baseline_exposure + 2)


def test_preview_is_rendered_once_then_served_from_disk(
    env: tuple[Renderer, EditStore, CatalogPhoto], monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer, edits, photo = env
    edit = edits.effective(photo)
    first = renderer.preview(photo, edit, 256)
    assert size_of(first) == (256, 160)
    assert renderer.preview_path(photo, edit, 256).is_file()

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("must not render again")

    monkeypatch.setattr(renderer_module, "render", fail)
    assert renderer.preview(photo, edit, 256) == first


def test_an_edit_gets_its_own_render(env: tuple[Renderer, EditStore, CatalogPhoto]) -> None:
    renderer, edits, photo = env
    before = renderer.preview(photo, edits.effective(photo), 256)
    edited = edits.save(photo, AdjustmentParams.model_validate({"tone": {"exposure": 1.0}}))
    after = renderer.preview(photo, edited, 256)
    brightness = lambda data: float(np.asarray(Image.open(io.BytesIO(data))).mean())  # noqa: E731
    assert brightness(after) > brightness(before) + 10


def test_prune_keeps_only_the_given_revisions(env: tuple[Renderer, EditStore, CatalogPhoto]) -> None:
    renderer, edits, photo = env
    default = edits.default(photo)
    renderer.preview(photo, default, 256)
    old = edits.save(photo, AdjustmentParams.model_validate({"tone": {"exposure": 0.5}}))
    renderer.preview(photo, old, 256)
    new = edits.save(photo, AdjustmentParams.model_validate({"tone": {"exposure": 0.7}}))
    renderer.preview(photo, new, 256)
    assert renderer.prune(photo.id, keep={new.revision, default.revision}) == 1
    assert not renderer.preview_path(photo, old, 256).exists()
    assert (
        renderer.preview_path(photo, new, 256).exists()
        and renderer.preview_path(photo, default, 256).exists()
    )


def test_thumbnails_do_not_evict_the_photo_being_edited(
    env: tuple[Renderer, EditStore, CatalogPhoto],
) -> None:
    renderer, edits, photo = env
    data = renderer.thumbnail(photo, edits.effective(photo))
    assert max(size_of(data)) == 320  # small originals are not enlarged
    assert renderer.linear.peek(photo.id) is None
    assert renderer.has_thumbnail(photo, edits.effective(photo))


def test_clear(env: tuple[Renderer, EditStore, CatalogPhoto]) -> None:
    renderer, edits, photo = env
    renderer.preview(photo, edits.effective(photo), 256)
    renderer.thumbnail(photo, edits.effective(photo))
    assert renderer.clear() == 2
    assert renderer.clear() == 0


def test_stats_are_measured_once_and_handed_on(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    guard = PathGuard(writable_roots=[workspace])
    photo = catalog_photo(write_jpeg(tmp_path / "photos" / "a.jpg", (200, 120, 60)))
    stored: list[tuple[str, dict[str, float], str]] = []
    renderer = Renderer(workspace / "cache", guard, remember_stats=lambda *a: stored.append(a))
    edits = EditStore(workspace / "edits", guard)
    renderer.thumbnail(photo, edits.effective(photo))  # measured on the decoded image
    renderer.preview(photo, edits.effective(photo), 256)  # on the working copy: same numbers, not again
    assert len(stored) == 1
    pid, stats, identity = stored[0]
    assert (pid, identity) == (photo.id, renderer.identity)
    assert renderer.stats(photo) == PhotoStats.model_validate(stats)
    assert renderer.anchors(photo) == ToneAnchors(black=stats["black"], white=stats["white"])


STORED = {
    "tone_black": -6.0,
    "tone_white": 1.0,
    "tone_middle": -2.0,
    "neutral_temperature": 5000.0,
    "neutral_tint": 0.0,
}


def test_stored_anchors_are_used_unless_another_engine_measured_them(
    env: tuple[Renderer, EditStore, CatalogPhoto], monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer, _, photo = env
    current = photo.model_copy(update={**STORED, "tone_anchors_identity": renderer.identity})

    def fail(*args: object) -> None:
        raise AssertionError("must not measure")

    with monkeypatch.context() as patched:
        patched.setattr(renderer_module, "measure_stats", fail)
        assert renderer.anchors(current) == ToneAnchors(black=-6.0, white=1.0)
        assert renderer.stats(current).middle == -2.0
    stale = current.model_copy(update={"tone_anchors_identity": "an older engine"})
    assert renderer.anchors(stale) != ToneAnchors(black=-6.0, white=1.0)
    # Anchors stored before P4.4 have no middle yet: everything is measured again in one pass.
    incomplete = current.model_copy(update={"tone_middle": None})
    assert renderer.stats(incomplete).middle != -2.0


def test_tone_sliders_use_the_stored_anchors(env: tuple[Renderer, EditStore, CatalogPhoto]) -> None:
    renderer, edits, photo = env
    edit = edits.save(photo, AdjustmentParams.model_validate({"tone": {"whites": 100}}))

    def with_white(white: float) -> CatalogPhoto:
        return photo.model_copy(
            update={
                **STORED,
                "tone_black": -8.0,
                "tone_white": white,
                "tone_anchors_identity": renderer.identity,
            }
        )

    low, high = with_white(-3.0), with_white(2.0)
    renderer.prune(photo.id, keep=set())
    first = renderer.preview(low, edit, 256)
    renderer.prune(photo.id, keep=set())
    assert renderer.preview(high, edit, 256) != first


@pytest.mark.golden
def test_real_raf_preview_is_upright_and_deterministic(sample_raw: Path, tmp_path: Path) -> None:
    guard = PathGuard(writable_roots=[tmp_path], protected_roots=[sample_raw.parent])
    photo = catalog_photo(sample_raw, SourceKind.RAW, camera="FUJIFILM X-T3", width=4170, height=6246)
    edit = EditStore(tmp_path / "edits", guard).effective(photo)
    first = Renderer(tmp_path / "cache1", guard).preview(photo, edit, 1600)
    second = Renderer(tmp_path / "cache2", guard).preview(photo, edit, 1600)
    assert first == second  # bit-identical across separate renders
    width, height = size_of(first)
    assert height == 1600 and width < height
