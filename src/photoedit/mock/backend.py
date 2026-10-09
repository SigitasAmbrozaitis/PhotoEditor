"""Mock parts of the backend that Phase 5 replaces: the built-in export presets are served from here, and
export jobs are simulated.

Export jobs run on the real job manager with the real photos, but each item only sleeps instead of rendering.
Nothing here reads photos or writes files.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models import ExportPreset, Job, JobKind, Photo

SECONDS_PER_ITEM = 0.4  # fake processing time per photo in a job

type PhotoLookup = Callable[[str], Photo]


class MockBackend:
    """The built-in export presets and simulated export jobs."""

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
        self._presets: dict[str, ExportPreset] = {p.id: p for p in BUILTIN_PRESETS}

    # ---- export presets

    def list_presets(self) -> list[ExportPreset]:
        return list(self._presets.values())

    def preset(self, preset_id: str) -> ExportPreset:
        try:
            return self._presets[preset_id]
        except KeyError:
            raise NotFoundError(f"export preset '{preset_id}' not found") from None

    # ---- simulated export

    def export_job(self, photo_ids: list[str], preset_id: str | None, destination: str) -> Job:
        photos = [self._photos(pid) for pid in photo_ids]
        preset_name = self.preset(preset_id).name if preset_id else "custom settings"
        noun = "photo" if len(photos) == 1 else "photos"

        def work(index: int) -> ItemResult:
            self._sleep(self._seconds_per_item)
            stem = photos[index].filename.rsplit(".", 1)[0]
            return ItemResult(output_path=f"{destination.rstrip('/')}/{stem}.jpg", message="simulated")

        return self._jobs.submit(
            JobKind.EXPORT,
            f"Export {len(photos)} {noun} ({preset_name}) (simulated)",
            [ItemSpec(filename=p.filename, photo_id=p.id) for p in photos],
            work,
            preset_id=preset_id,
            destination=destination,
        )
