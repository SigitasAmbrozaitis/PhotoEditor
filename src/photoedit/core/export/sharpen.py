"""Output sharpening: a final unsharp mask for the medium the export is for, after resizing.

Resizing softens edges, and paper softens them again (ink spreads, more on matte than on glossy paper), so
exports get a last, fixed amount of sharpening in the spirit of Lightroom's output sharpening. It uses the
pipeline's own sharpening stage, with a radius in output pixels. For paper the radius grows with the print
resolution, so it covers the same distance on the page at any PPI.
"""

from __future__ import annotations

from photoedit.core.render import stages
from photoedit.core.render.stages import F32
from photoedit.models.adjustments import Sharpening
from photoedit.models.export import OutputSharpening, SharpenAmount, SharpenFor

_PAPER_PPI = 300  # the paper radii below are for 300 PPI

# target → (radius in output pixels, detail, amount per strength)
TABLE: dict[SharpenFor, tuple[float, int, dict[SharpenAmount, int]]] = {
    SharpenFor.SCREEN: (0.6, 25, {SharpenAmount.LOW: 25, SharpenAmount.STANDARD: 45, SharpenAmount.HIGH: 70}),
    SharpenFor.GLOSSY_PAPER: (
        0.8,
        25,
        {SharpenAmount.LOW: 35, SharpenAmount.STANDARD: 60, SharpenAmount.HIGH: 90},
    ),
    SharpenFor.MATTE_PAPER: (
        1.1,
        30,
        {SharpenAmount.LOW: 45, SharpenAmount.STANDARD: 75, SharpenAmount.HIGH: 110},
    ),
}


def radius(settings: OutputSharpening, ppi: int) -> float:
    """The unsharp mask's radius in output pixels (0 when there is no output sharpening)."""
    if settings.target == SharpenFor.NONE:
        return 0.0
    base = TABLE[settings.target][0]
    return base if settings.target == SharpenFor.SCREEN else base * ppi / _PAPER_PPI


def output_sharpen(encoded: F32, settings: OutputSharpening, ppi: int) -> F32:
    """Sharpen the encoded output pixels for the export's medium."""
    if settings.target == SharpenFor.NONE:
        return encoded
    base, detail, amounts = TABLE[settings.target]
    params = Sharpening(amount=amounts[settings.amount], radius=base, detail=detail, masking=0)
    return stages.sharpen(encoded, params, radius(settings, ppi) / base)
