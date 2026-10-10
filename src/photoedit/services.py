"""Wires the core together from settings. Every front-end (HTTP API, CLI, later MCP) builds one of these."""

from __future__ import annotations

from photoedit.config import Settings
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.core.styles import StyleLibrary
from photoedit.core.styling import Styling
from photoedit.mock import MockBackend
from photoedit.mock.backend import SECONDS_PER_ITEM
from photoedit.safety import PathGuard, guard_from_settings

CATALOG_FILE = "catalog.sqlite"


class Services:
    def __init__(self, settings: Settings, *, mock_seconds_per_item: float = SECONDS_PER_ITEM) -> None:
        self.settings = settings
        self.guard: PathGuard = guard_from_settings(settings)
        self.jobs = JobManager()
        self.catalog = Catalog(settings.workspace_dir / CATALOG_FILE, self.guard)
        self.cache = ImageCache(settings.cache_dir, self.guard)
        self.styles = StyleLibrary(settings.styles_dir, self.guard)
        self.library = Library(
            self.catalog,
            self.cache,
            self.jobs,
            self.guard,
            suggested_folder=settings.sample_photos_dir,
            styles=self.styles,
        )
        self.styling = Styling(self.library, self.styles, self.jobs, self.guard)
        self.mock = MockBackend(
            self.jobs, lambda pid: self.library.photo(pid).to_photo(), seconds_per_item=mock_seconds_per_item
        )

    def close(self) -> None:
        self.jobs.shutdown()
        self.catalog.close()
