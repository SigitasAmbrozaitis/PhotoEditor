from __future__ import annotations

import os
from pathlib import Path

import pytest

from photoedit.config import Settings
from photoedit.safety import PathGuard, WriteNotAllowedError, guard_from_settings


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    out = tmp_path / "output"
    photos = tmp_path / "photos"
    other = tmp_path / "other"
    for d in (out, photos, other):
        d.mkdir()
    return out, photos, other


def test_write_inside_writable_root_allowed(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    guard = PathGuard([out])
    assert guard.is_writable(out / "a.jpg")
    assert guard.is_writable(out / "deep" / "nested" / "b.jpg")  # not existing yet
    assert guard.assert_writable(out / "a.jpg") == Path(os.path.realpath(out / "a.jpg"))


def test_root_itself_is_writable(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    assert PathGuard([out]).is_writable(out)


def test_write_outside_roots_denied(roots: tuple[Path, Path, Path]) -> None:
    out, _, other = roots
    guard = PathGuard([out])
    assert not guard.is_writable(other / "x.jpg")
    with pytest.raises(WriteNotAllowedError, match="outside"):
        guard.assert_writable(other / "x.jpg")


def test_no_roots_denies_everything(tmp_path: Path) -> None:
    assert not PathGuard().is_writable(tmp_path / "x")


def test_sibling_with_common_prefix_denied(tmp_path: Path) -> None:
    # "output2" starts with "output" as a string but is not inside it.
    guard = PathGuard([tmp_path / "output"])
    assert not guard.is_writable(tmp_path / "output2" / "x.jpg")


def test_dotdot_traversal_denied(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    guard = PathGuard([out])
    assert not guard.is_writable(out / ".." / "other" / "x.jpg")
    assert guard.is_writable(out / "sub" / ".." / "x.jpg")


def test_protected_root_wins_over_writable(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    guard = PathGuard(writable_roots=[tmp_path], protected_roots=[photos])
    assert guard.is_writable(tmp_path / "x.jpg")
    assert not guard.is_writable(photos / "DSCF0001.RAF")
    with pytest.raises(WriteNotAllowedError, match="protected"):
        guard.assert_writable(photos / "DSCF0001.xmp")


def test_registering_export_destination_at_runtime(roots: tuple[Path, Path, Path]) -> None:
    out, _, other = roots
    guard = PathGuard([out])
    assert not guard.is_writable(other / "x.jpg")
    guard.allow_writes_to(other)
    assert guard.is_writable(other / "x.jpg")
    guard.allow_writes_to(other)  # idempotent
    assert len(guard.writable_roots) == 2


def test_cannot_register_export_inside_protected_folder(roots: tuple[Path, Path, Path]) -> None:
    out, photos, _ = roots
    guard = PathGuard([out], [photos])
    guard.allow_writes_to(photos / "exports")
    assert not guard.is_writable(photos / "exports" / "x.jpg")


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics")
def test_case_insensitive_on_windows(roots: tuple[Path, Path, Path]) -> None:
    out, photos, _ = roots
    guard = PathGuard([out], [photos])
    assert guard.is_writable(Path(str(out).upper()) / "a.jpg")
    assert not guard.is_writable(Path(str(photos).upper()) / "a.RAF")


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics")
def test_forward_slashes_on_windows(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    assert PathGuard([out]).is_writable(Path(out.as_posix() + "/a.jpg"))


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics")
def test_unc_and_other_drive_denied(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    guard = PathGuard([out])
    assert not guard.is_writable(Path(r"\\server\share\x.jpg"))
    other_drive = "Z:\\" if not str(out).upper().startswith("Z:") else "Y:\\"
    assert not guard.is_writable(Path(other_drive) / "x.jpg")


def test_symlink_escaping_root_denied(roots: tuple[Path, Path, Path]) -> None:
    out, _, other = roots
    link = out / "link"
    try:
        link.symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this system")
    assert not PathGuard([out]).is_writable(link / "x.jpg")


def test_symlink_into_protected_folder_denied(roots: tuple[Path, Path, Path]) -> None:
    out, photos, _ = roots
    link = out / "photos-link"
    try:
        link.symlink_to(photos, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this system")
    assert not PathGuard([out], [photos]).is_writable(link / "x.RAF")


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are Windows-only")
def test_junction_escaping_root_denied(roots: tuple[Path, Path, Path]) -> None:
    # Junctions need no special privilege on Windows, so this always runs where symlink tests may skip.
    import _winapi

    out, photos, other = roots
    _winapi.CreateJunction(str(other), str(out / "junction-out"))
    _winapi.CreateJunction(str(photos), str(out / "junction-photos"))
    guard = PathGuard([out], [photos])
    assert not guard.is_writable(out / "junction-out" / "x.jpg")
    assert not guard.is_writable(out / "junction-photos" / "x.RAF")


def test_guard_from_settings(settings: Settings, tmp_path: Path) -> None:
    guard = guard_from_settings(settings)
    for d in settings.writable_dirs:
        assert guard.is_writable(d / "file")
    assert not guard.is_writable(tmp_path / "pyproject.toml")  # project root itself is not writable
    assert guard.protected_roots == ()


def test_guard_from_settings_protects_sample_photos(tmp_path: Path) -> None:
    from photoedit.config import load_settings

    s = load_settings(
        tmp_path / "missing.toml", project_root=tmp_path, sample_photos_dir=tmp_path / "output" / "p"
    )
    guard = guard_from_settings(s)
    assert guard.is_writable(tmp_path / "output" / "x.jpg")
    assert not guard.is_writable(tmp_path / "output" / "p" / "x.RAF")


def test_write_atomic_writes_inside_writable_root(roots: tuple[Path, Path, Path]) -> None:
    out, _, _ = roots
    guard = PathGuard(writable_roots=[out])
    target = guard.write_atomic(out / "sub" / "a.bin", b"hello")
    assert target.read_bytes() == b"hello"
    guard.write_atomic(out / "sub" / "a.bin", b"replaced")
    assert target.read_bytes() == b"replaced"
    assert [p.name for p in target.parent.iterdir()] == ["a.bin"]  # no temp files left behind


def test_write_atomic_refuses_protected_and_outside(roots: tuple[Path, Path, Path]) -> None:
    out, photos, other = roots
    guard = PathGuard(writable_roots=[out, photos], protected_roots=[photos])
    with pytest.raises(WriteNotAllowedError):
        guard.write_atomic(photos / "x.jpg", b"x")
    with pytest.raises(WriteNotAllowedError):
        guard.write_atomic(other / "x.jpg", b"x")
    assert list(photos.iterdir()) == [] and list(other.iterdir()) == []


@pytest.mark.parametrize(
    ("returned", "expected"),
    [
        (r"\\?\C:\work\cache\thumbs\a.jpg", r"C:\work\cache\thumbs\a.jpg"),
        (r"\\?\UNC\server\share\a.jpg", r"\\server\share\a.jpg"),
        (r"C:\work\cache\a.jpg", r"C:\work\cache\a.jpg"),
    ],
)
def test_extended_length_prefix_is_stripped(
    monkeypatch: pytest.MonkeyPatch, returned: str, expected: str
) -> None:
    """Windows realpath can keep the extended-length prefix while another thread creates the folder."""
    from photoedit import safety

    monkeypatch.setattr(safety.os.path, "realpath", lambda p: returned)
    assert safety._normalize(Path("anything")) == Path(expected)


def test_prefixed_realpath_still_counts_as_inside_the_root(
    roots: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from photoedit import safety

    out, _, _ = roots
    guard = PathGuard(writable_roots=[out])
    real = os.path.realpath
    monkeypatch.setattr(
        safety.os.path, "realpath", lambda p: "\\\\?\\" + real(p) if "thumbs" in str(p) else real(p)
    )
    assert guard.is_writable(out / "thumbs" / "a.jpg")


def test_unresolvable_paths_are_never_writable(
    roots: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """realpath can raise for an unreachable network share under load: that must deny, not crash."""
    from photoedit import safety

    out, _, _ = roots
    guard = PathGuard(writable_roots=[out])
    real = os.path.realpath

    def flaky(path: object) -> str:
        if "server" in str(path):
            raise OSError(121, "The semaphore timeout period has expired")
        return real(path)  # type: ignore[arg-type]

    monkeypatch.setattr(safety.os.path, "realpath", flaky)
    assert not guard.is_writable(Path(r"\server\share\x.jpg"))
    with pytest.raises(WriteNotAllowedError, match="can't be resolved"):
        guard.assert_writable(Path(r"\server\share\x.jpg"))


def test_revoke_and_protected_root_of(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    out = tmp_path / "out"
    guard = PathGuard(protected_roots=[photos])
    guard.allow_writes_to(out)
    assert guard.is_writable(out / "a.jpg")
    guard.revoke(out)
    assert not guard.is_writable(out / "a.jpg")
    guard.revoke(out)  # revoking twice is harmless
    assert guard.protected_root_of(photos / "sub" / "x.jpg") == photos.resolve()
    assert guard.protected_root_of(out) is None
