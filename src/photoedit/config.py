"""Application settings.

Precedence (lowest → highest): built-in defaults → ``config.local.toml``
→ ``PHOTOEDIT_*`` environment variables
→ explicit keyword arguments.

Relative directory paths are resolved against ``project_root``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

# src/photoedit/config.py -> project root is two levels above the package directory.
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_CONFIG_NAME = "config.local.toml"


class Settings(BaseSettings):
    """Effective configuration of the tool."""

    model_config = SettingsConfigDict(env_prefix="PHOTOEDIT_", extra="forbid", validate_default=True)

    project_root: Path = DEFAULT_PROJECT_ROOT

    # Tool-owned data folders (writable). Relative paths resolve against project_root.
    workspace_dir: Path = Path("workspace")
    styles_dir: Path = Path("styles")
    presets_dir: Path = Path("export-presets")
    output_dir: Path = Path("output")
    cache_dir: Path = Path("cache")
    ui_dist_dir: Path = Path("ui/dist")

    # Folder with sample photos used for development and tests. Always read-only.
    sample_photos_dir: Path | None = None
    # Folders of varied real photos for developing and testing styles (P4.1). Always read-only.
    style_sample_dirs: list[Path] = Field(default_factory=list)

    # Export (Phase 5). Copyright and creator are written into exported files when the preset leaves them
    # empty; {year} in the copyright becomes the photo's capture year.
    export_copyright: str | None = Field(default=None, max_length=200)
    export_creator: str | None = Field(default=None, max_length=200)
    # Worker processes for exports. None = automatic (see core.export.service.auto_workers).
    export_workers: int | None = Field(default=None, ge=1, le=32)

    # Local web server.
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)

    @model_validator(mode="after")
    def _resolve_paths(self) -> Self:
        root = self.project_root.expanduser().resolve()
        self.project_root = root
        for name in ("workspace_dir", "styles_dir", "presets_dir", "output_dir", "cache_dir", "ui_dist_dir"):
            value: Path = getattr(self, name)
            setattr(self, name, _absolute(value, root))
        if self.sample_photos_dir is not None:
            self.sample_photos_dir = _absolute(self.sample_photos_dir, root)
        self.style_sample_dirs = [_absolute(p, root) for p in self.style_sample_dirs]
        return self

    @property
    def photo_dirs(self) -> tuple[Path, ...]:
        """Configured photo folders (never written to)."""
        sample = (self.sample_photos_dir,) if self.sample_photos_dir is not None else ()
        return (*sample, *self.style_sample_dirs)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Earlier sources win. The TOML file path comes from model_config["toml_file"] (set by load_settings).
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))

    @property
    def writable_dirs(self) -> tuple[Path, ...]:
        """Folders the tool itself may write into."""
        return (self.workspace_dir, self.styles_dir, self.presets_dir, self.output_dir, self.cache_dir)


def _absolute(path: Path, root: Path) -> Path:
    path = path.expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def load_settings(config_file: Path | None = None, **overrides: object) -> Settings:
    """Load settings, reading ``config_file`` (default: ``<project_root>/config.local.toml``) if it exists."""
    toml_path = config_file if config_file is not None else DEFAULT_PROJECT_ROOT / LOCAL_CONFIG_NAME

    class _FileSettings(Settings):
        model_config = SettingsConfigDict(toml_file=toml_path)

    return _FileSettings(**overrides)  # type: ignore[arg-type]
