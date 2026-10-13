from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from photoedit.models import JobRequest
from photoedit.models.adjustments import CropRect
from photoedit.models.export import ExportSettings
from photoedit.models.job import PrepareExportRequest
from photoedit.models.review import (
    ExportReview,
    ReviewCandidate,
    ReviewExportRequest,
    ReviewExportScope,
    ReviewItem,
    ReviewItemUpdate,
    ReviewReason,
    ReviewRule,
    ReviewSettings,
    ReviewStatus,
    ReviewSubjectUpdate,
    ZoomLimits,
)
from photoedit.models.subject import SubjectBox

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
BOX = SubjectBox(left=0.1, top=0.2, right=0.4, bottom=0.6)


def _item(photo_id: str, status: ReviewStatus, *, approved: bool = False) -> ReviewItem:
    reasons = [ReviewReason(code=ReviewRule.UNCERTAIN, text="score 0.42")] if status == "check" else []
    return ReviewItem(
        photo_id=photo_id,
        filename=f"{photo_id}.RAF",
        status=status,
        reasons=reasons,
        approved=approved,
        framing="f1",
        subject_box=BOX,
        candidates=[ReviewCandidate(index=0, box=BOX, kind="car", score=0.42, chosen=True)],
        crop=CropRect(left=0.2, right=0.7),
        zoom=1.2,
        auto_zoom=1.2,
        limits=ZoomLimits(fast=1.54, quality=3.08),
        decode="half",
        width=1080,
        height=1350,
        revision="r1",
    )


def _review() -> ExportReview:
    return ExportReview(
        id="abcdef123456",
        created_at=NOW,
        updated_at=NOW,
        preset_id="instagram-portrait",
        settings=ExportSettings(),
        destination="C:/out",
        items=[
            _item("a", ReviewStatus.READY),
            _item("b", ReviewStatus.CHECK),
            _item("c", ReviewStatus.CHECK, approved=True),
            _item("d", ReviewStatus.UNUSABLE),
        ],
    )


def test_review_settings_defaults() -> None:
    settings = ReviewSettings()
    assert (settings.min_score, settings.ambiguity) == (0.5, 0.75)
    assert all([settings.no_subject, settings.uncertain, settings.ambiguous, settings.cut_off])
    assert settings.zoom_limit


@pytest.mark.parametrize(
    "bad",
    [{"min_score": 1.1}, {"min_score": -0.1}, {"ambiguity": 0.05}, {"ambiguity": 1.5}, {"strict": True}],
)
def test_review_settings_ranges(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReviewSettings.model_validate(bad)


def test_counts_and_exportable() -> None:
    review = _review()
    assert review.counts.model_dump() == {"total": 4, "ready": 1, "check": 1, "approved": 1, "unusable": 1}
    assert [i.photo_id for i in review.items if i.exportable] == ["a", "c"]


def test_review_round_trip_without_counts() -> None:
    review = _review()
    stored = review.model_dump_json(exclude={"counts"})
    assert ExportReview.model_validate_json(stored) == review
    assert "counts" in review.model_dump()


def test_review_id_format() -> None:
    with pytest.raises(ValidationError, match="id"):
        _review().model_validate({**_review().model_dump(exclude={"counts"}), "id": "../x"})


def test_item_zoom_override_range() -> None:
    with pytest.raises(ValidationError, match="zoom_override"):
        _item("a", ReviewStatus.READY).model_validate(
            {**_item("a", ReviewStatus.READY).model_dump(), "zoom_override": 0.5}
        )


def test_item_update_rules() -> None:
    assert ReviewItemUpdate.model_validate({"zoom": None}).model_fields_set == {"zoom"}
    assert ReviewItemUpdate(zoom=2.0).zoom == 2.0
    assert ReviewItemUpdate(approved=False).approved is False
    with pytest.raises(ValidationError, match="give zoom or approved"):
        ReviewItemUpdate()
    with pytest.raises(ValidationError, match="approved must be true or false"):
        ReviewItemUpdate.model_validate({"approved": None})
    with pytest.raises(ValidationError, match="zoom"):
        ReviewItemUpdate(zoom=0.9)
    with pytest.raises(ValidationError, match="zoom"):
        ReviewItemUpdate(zoom=21)


def test_subject_update_one_of() -> None:
    assert ReviewSubjectUpdate(candidate=2).candidate == 2
    assert ReviewSubjectUpdate(box=BOX).box == BOX
    assert ReviewSubjectUpdate.model_validate({"box": None}).box is None
    for bad in ({}, {"candidate": 1, "box": None}, {"candidate": None}, {"candidate": -1}):
        with pytest.raises(ValidationError):
            ReviewSubjectUpdate.model_validate(bad)


def test_export_request_scope() -> None:
    assert ReviewExportRequest().scope == ReviewExportScope.APPROVED
    with pytest.raises(ValidationError):
        ReviewExportRequest.model_validate({"scope": "some"})


def test_prepare_export_request() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(JobRequest)
    request = adapter.validate_python(
        {"kind": "prepare_export", "photo_ids": ["a"], "settings": {}, "destination": "C:/out"}
    )
    assert isinstance(request, PrepareExportRequest)
    assert request.style_id is None
    with pytest.raises(ValidationError, match="even_out needs a style"):
        PrepareExportRequest(photo_ids=["a"], settings=ExportSettings(), destination="C:/o", even_out=True)


def test_review_read_back_with_its_counts() -> None:
    review = _review()
    assert ExportReview.model_validate_json(review.model_dump_json()) == review
