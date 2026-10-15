"""Pre-export review (Phase 6c): a prepared export whose doubtful photos wait for the user's decision.

Prepare frames every photo the way the export will and sorts it: **Ready** (the tool is sure), **Check** (one
or more reasons, each a rule from ``ReviewSettings``) or **unusable** (it can't be exported). A Check photo is
exported once the user approves it, or fixes it (another subject, a zoom), which is also an approval.

Boxes and crops in a review item are normalized to the **edited photo** (after its own crop): the picture the
review shows. Choosing a subject is saved to the photo's edit in upright coordinates, like the crop tool's.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from photoedit.models.adjustments import CropRect
from photoedit.models.export import DecodeUsed, ExportSettings
from photoedit.models.subject import FoundCandidate, SubjectBox, SubjectKind, SubjectSource

# The highest zoom anyone may ask for; each photo's own quality limit is usually far below it.
MAX_ZOOM = 20.0


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class ReviewRule(StrEnum):
    NO_SUBJECT = "no_subject"  # nothing recognized: centered, or framed on the camera's focus point
    UNCERTAIN = "uncertain"  # the detected subject scores below min_score
    AMBIGUOUS = "ambiguous"  # another recognized candidate nearly as good
    CUT_OFF = "cut_off"  # the aspect crop can't hold the whole subject
    ZOOM_LIMIT = "zoom_limit"  # the subject stays smaller than wanted even at the quality limit
    CHANGED = "changed"  # the framing changed after it was approved
    UNUSABLE = "unusable"  # the export can't be made (original missing, broken style)


class ReviewSettings(_Model):
    """How strict the review is: which rules put a photo in Check, and their thresholds."""

    no_subject: bool = Field(default=True, description="Check photos without a recognized subject.")
    uncertain: bool = Field(default=True, description="Check detected subjects scoring below min_score.")
    min_score: float = Field(default=0.5, ge=0, le=1, description="The lowest score trusted without a look.")
    ambiguous: bool = Field(default=True, description="Check photos with a rival nearly as good.")
    ambiguity: float = Field(
        default=0.75,
        ge=0.1,
        le=1,
        description="A rival scoring at least this share of the subject's score makes the photo ambiguous.",
    )
    cut_off: bool = Field(default=True, description="Check photos whose crop can't hold the whole subject.")
    zoom_limit: bool = Field(
        default=True, description="Check photos whose subject stays too small even at the quality limit."
    )


class ReviewReason(_Model):
    code: ReviewRule
    text: str = Field(description="The reason in words, for this photo.")


class ReviewStatus(StrEnum):
    READY = "ready"
    CHECK = "check"
    UNUSABLE = "unusable"


# The review lists what detection found in the same shape as the Photo view's analysis.
ReviewCandidate = FoundCandidate


class FramePosition(_Model):
    """Where the crop's center was put by hand, normalized to the edited photo. The crop sits as close to it
    as the photo allows at any zoom."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ZoomLimits(_Model):
    fast: float = Field(ge=1, description="The highest zoom a half-size decode still covers (fast export).")
    quality: float = Field(ge=1, description="The highest zoom without enlarging (the crop ≥ the output).")


class ReviewItem(_Model):
    photo_id: str
    filename: str
    status: ReviewStatus
    reasons: list[ReviewReason] = Field(default_factory=list)
    approved: bool = Field(default=False, description="The user approved this framing (Check photos).")
    approved_framing: str | None = Field(
        default=None, description="The framing the approval was given for; a different one drops it."
    )
    framing: str = Field(description="Identifies the framing (the crop and the output size) to compare.")
    subject: SubjectSource = SubjectSource.NONE
    subject_kind: SubjectKind | None = None
    subject_score: float | None = Field(default=None, ge=0, le=1)
    subject_box: SubjectBox | None = Field(default=None, description="Normalized to the edited photo.")
    candidates: list[ReviewCandidate] = Field(default_factory=list, description="Best first.")
    focus: SubjectBox | None = Field(
        default=None, description="Where the camera focused (a small box), normalized to the edited photo."
    )
    position: FramePosition | None = Field(
        default=None, description="The crop's center, set by hand in the review; none = placed by the rules."
    )
    crop: CropRect = Field(description="The export's crop, normalized to the edited photo.")
    zoom: float = Field(ge=1, description="The zoom the export uses.")
    auto_zoom: float = Field(ge=1, description="What automatic zoom chose (1 when it is off or not used).")
    zoom_override: float | None = Field(default=None, ge=1, le=MAX_ZOOM, description="Set in the review.")
    limits: ZoomLimits
    decode: DecodeUsed
    width: int = Field(ge=1, description="Output width.")
    height: int = Field(ge=1, description="Output height.")
    warnings: list[str] = Field(default_factory=list)
    revision: str = Field(description="Changes whenever the framing preview changes (for caching).")

    @property
    def exportable(self) -> bool:
        """Exported by Export Approved: Ready, or Check and approved."""
        return self.status == ReviewStatus.READY or (self.status == ReviewStatus.CHECK and self.approved)


class ReviewCounts(_Model):
    total: int = Field(ge=0)
    ready: int = Field(ge=0)
    check: int = Field(ge=0, description="Check photos not approved yet.")
    approved: int = Field(ge=0, description="Check photos the user approved.")
    unusable: int = Field(ge=0)


def count(items: list[ReviewItem]) -> ReviewCounts:
    check = [i for i in items if i.status == ReviewStatus.CHECK]
    return ReviewCounts(
        total=len(items),
        ready=sum(i.status == ReviewStatus.READY for i in items),
        check=sum(not i.approved for i in check),
        approved=sum(i.approved for i in check),
        unusable=sum(i.status == ReviewStatus.UNUSABLE for i in items),
    )


class ExportReview(_Model):
    """A prepared export: what it will write, photo by photo, and the user's decisions so far."""

    id: str = Field(pattern=r"^[a-z0-9]{12}$")
    created_at: datetime
    updated_at: datetime
    preset_id: str | None = None
    style_id: str | None = Field(default=None, description="The style applied before preparing, if any.")
    settings: ExportSettings
    destination: str = Field(description="The destination folder, absolute.")
    items: list[ReviewItem]

    @model_validator(mode="before")
    @classmethod
    def _derived_counts(cls, data: Any) -> Any:
        # The counts are computed from the items; a review read back from the API carries them.
        if isinstance(data, dict) and "counts" in data:
            return {k: v for k, v in data.items() if k != "counts"}
        return data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def counts(self) -> ReviewCounts:
        return count(self.items)


class ReviewSummary(_Model):
    id: str
    created_at: datetime
    updated_at: datetime
    preset_id: str | None
    destination: str
    counts: ReviewCounts


class ReviewItemUpdate(_Model):
    """Fields left out stay as they are. ``zoom: null`` goes back to the automatic zoom, ``position: null``
    to the frame placed by the rules. A zoom or a position is a decision, so it approves the photo."""

    model_config = ConfigDict(extra="forbid")

    zoom: float | None = Field(default=None, ge=1, le=MAX_ZOOM)
    position: FramePosition | None = None
    approved: bool | None = None

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("give zoom, position or approved")
        if "approved" in self.model_fields_set and self.approved is None:
            raise ValueError("approved must be true or false")
        return self


class ReviewSubjectUpdate(_Model):
    """Choose a detected candidate (``candidate``), draw a box (``box``, normalized to the edited photo), or
    ``box: null`` to go back to the detected subject."""

    model_config = ConfigDict(extra="forbid")

    candidate: int | None = Field(default=None, ge=0)
    box: SubjectBox | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        given = self.model_fields_set
        if given == {"candidate"} and self.candidate is not None:
            return self
        if given == {"box"}:
            return self
        raise ValueError("give either candidate (a number) or box (a box, or null for the detected subject)")


class ReviewExportScope(StrEnum):
    APPROVED = "approved"  # Ready + approved Check photos
    ALL = "all"  # also the Check photos not approved (the tool's framing)


class ReviewExportRequest(_Model):
    scope: ReviewExportScope = ReviewExportScope.APPROVED


class ZoomFrame(_Model):
    zoom: float = Field(ge=1)
    crop: CropRect = Field(description="The export's crop at this zoom, normalized to the edited photo.")


class ReviewFrames(_Model):
    """The export's crop at each zoom step from 1 to the quality limit, for the item's current subject and
    position: the review moves the frame along these while the zoom slider is dragged."""

    photo_id: str
    frames: list[ZoomFrame]
