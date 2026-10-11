"""Evaluating subject detection against labels (P6b.9): the judging rules, the report and the CLI."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from helpers import write_jpeg
from photoedit import cli
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.scan import SourceKind
from photoedit.core.subject.evaluate import (
    LabeledPhoto,
    contact_sheet,
    evaluate,
    iou,
    judge,
    kept_share,
    load_labels,
    report,
    scores,
)
from photoedit.models.adjustments import CropRect
from photoedit.models.subject import SubjectBox, SubjectInfo, SubjectKind, SubjectSource

LABELS = Path(__file__).parent / "data" / "subject-labels.json"


def box(left: float, top: float, right: float, bottom: float) -> SubjectBox:
    return SubjectBox(left=left, top=top, right=right, bottom=bottom)


def found(b: SubjectBox | None) -> SubjectInfo:
    if b is None:
        return SubjectInfo(source=SubjectSource.NONE)
    return SubjectInfo(source=SubjectSource.DETECTED, box=b, kind=SubjectKind.CAR, score=0.9)


def photo(name: str, width: int = 4000, height: int = 6000) -> CatalogPhoto:
    return CatalogPhoto(
        id=name,
        sha256="0" * 64,
        path=Path(f"C:/p/{name}.RAF"),
        kind=SourceKind.RAW,
        file_size=1,
        mtime_ns=1,
        width=width,
        height=height,
    )


def test_the_committed_labels_are_valid() -> None:
    labels = load_labels(LABELS)
    assert len(labels.photos) >= 40
    assert {p.folder for p in labels.photos} == {"2026-07-26", "2026-08-11", "2026-08-16", "2026-08-17"}
    assert any(p.box is None for p in labels.photos)
    for p in labels.photos:
        assert p.box is None or p.subject is not None  # every box passes SubjectBox's checks


def test_iou_and_kept_share() -> None:
    a = box(0, 0, 0.5, 0.5)
    assert iou(a, a) == pytest.approx(1)
    assert iou(a, box(0.25, 0, 0.75, 0.5)) == pytest.approx(1 / 3)
    assert iou(a, box(0.6, 0.6, 0.9, 0.9)) == 0
    assert kept_share(a, CropRect(left=0, top=0, right=0.25, bottom=1)) == pytest.approx(0.5)


CENTERED = CropRect(left=0.1, top=0, right=0.9, bottom=1)


@pytest.mark.parametrize(
    ("label", "detected", "hit"),
    [
        (box(0.4, 0.4, 0.5, 0.5), box(0.3, 0.3, 0.9, 0.9), True),  # the label's center is inside
        (box(0.4, 0.4, 0.6, 0.6), box(0.52, 0.4, 0.62, 0.6), True),  # IoU 0.36 without the center
        (box(0.4, 0.4, 0.5, 0.5), box(0.6, 0.6, 0.7, 0.7), False),
        (box(0.4, 0.4, 0.5, 0.5), None, False),
    ],
)
def test_hits(label: SubjectBox, detected: SubjectBox | None, hit: bool) -> None:
    assert judge(label, found(detected), CENTERED, CENTERED)[0] is hit


def test_crops_must_keep_95_percent_of_the_label() -> None:
    label = box(0.0, 0.4, 0.2, 0.5)
    inside = CropRect(left=0, top=0, right=0.8, bottom=1)
    clipped = CropRect(left=0.02, top=0, right=0.82, bottom=1)  # 10 % of the label cut off
    assert judge(label, found(label), inside, CENTERED) == (True, True)
    assert judge(label, found(label), clipped, CENTERED) == (True, False)
    # A subject taller than any crop of the ratio: judged against the most a crop of that size could keep.
    tall = box(0.1, 0.0, 0.9, 1.0)
    crop = CropRect(left=0.1, top=0.08, right=0.9, bottom=0.92)
    assert judge(tall, found(tall), crop, CENTERED) == (True, True)
    assert (
        judge(tall, found(tall), CropRect(left=0.2, top=0.08, right=1.0, bottom=0.92), CENTERED)[1] is False
    )


def test_no_subject_labels_pass_when_nothing_is_found_or_the_crop_is_centered() -> None:
    assert judge(None, found(None), CENTERED, CENTERED) == (True, True)
    assert judge(None, found(box(0.4, 0.4, 0.6, 0.6)), CENTERED, CENTERED) == (True, True)
    moved = CropRect(left=0.2, top=0, right=1.0, bottom=1)
    assert judge(None, found(box(0.8, 0.4, 0.9, 0.6)), moved, CENTERED) == (False, False)


def test_evaluate_report_and_sheet() -> None:
    labels = [
        LabeledPhoto(folder="rally", file="a.RAF", box=(0.6, 0.4, 0.7, 0.45)),
        LabeledPhoto(folder="rally", file="b.RAF", box=(0.1, 0.4, 0.2, 0.45), note="tiny car"),
        LabeledPhoto(folder="sunsets", file="c.RAF", box=None),
    ]
    detections = {
        "a": found(box(0.58, 0.38, 0.72, 0.47)),
        "b": found(box(0.7, 0.1, 0.9, 0.2)),  # the wrong thing
        "c": found(None),
    }
    photos = [photo("a"), photo("b"), photo("c")]
    results = evaluate(labels, photos, lambda p: detections[p.id], workers=2)
    assert [(r.hit, r.crop_ok) for r in results] == [(True, True), (False, True), (True, True)]
    rally, sunsets = scores(results)
    assert (rally.photos, rally.hits, rally.crops, rally.passed) == (2, 1, 2, False)
    assert sunsets.passed
    text = report(results)
    assert "MISSED" in text and "rally/b.RAF (tiny car): detection missed; found detected car" in text

    def thumbnail(_: CatalogPhoto) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (200, 300), (90, 90, 90)).save(buffer, "JPEG")
        return buffer.getvalue()

    sheet = Image.open(io.BytesIO(contact_sheet(results, thumbnail)))
    assert sheet.size == (8 * 300, 316)


def test_cli_eval(tmp_path: Path) -> None:
    folder = tmp_path / "2026-01-01"
    write_jpeg(folder / "plain.jpg", (128, 128, 128), size=(300, 200))
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "version": 1,
                "photos": [
                    {"folder": "2026-01-01", "file": "plain.jpg", "box": None},
                    {"folder": "elsewhere", "file": "x.jpg", "box": None},
                ],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "c.toml"
    config.write_text(
        f'project_root = "{(tmp_path / "project").as_posix()}"\n'
        f'style_sample_dirs = ["{folder.as_posix()}"]\n',
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        cli.app, ["subject", "eval", "--labels", str(labels), "--config", str(config)]
    )
    assert result.exit_code == 0, result.output
    assert "Skipping labels of folders that aren't configured or present: elsewhere" in result.output
    assert "2026-01-01" in result.output and "100%" in result.output
    assert (tmp_path / "project" / "output" / "contact-sheets" / "subject-eval.jpg").is_file()
