"""Generate static manuscript schematics from the frozen study design."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "pilot-v1" / "figures"

INK = "#18324A"
LIGHT = "#F4F7FA"


def _font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("C:/Windows/Fonts") / ("calibrib.ttf" if bold else "calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _box(draw, xy, text, fill, font_size=34):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=24, fill=fill, outline=INK, width=4)
    font = _font(font_size)
    lines = text.split("\n")
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [box[3] - box[1] for box in boxes]
    total = sum(heights) + 10 * (len(lines) - 1)
    y = (y0 + y1 - total) / 2
    for line, box, height in zip(lines, boxes, heights, strict=True):
        width = box[2] - box[0]
        draw.text(((x0 + x1 - width) / 2, y), line, font=font, fill=INK)
        y += height + 10


def _arrow(draw, start, end, color=INK, width=6):
    draw.line([start, end], fill=color, width=width)
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    arrow_length = 24
    arrow_half_width = 14
    base_x = x1 - arrow_length * ux
    base_y = y1 - arrow_length * uy
    draw.polygon(
        [
            (x1, y1),
            (base_x + arrow_half_width * px, base_y + arrow_half_width * py),
            (base_x - arrow_half_width * px, base_y - arrow_half_width * py),
        ],
        fill=color,
    )


def study_design() -> None:
    image = Image.new("RGB", (3600, 1560), "white")
    draw = ImageDraw.Draw(image)
    boxes = [
        ((100, 180, 730, 550), "120 prespecified questions\n60 chemical + 60 pharmaceutical", LIGHT),
        ((990, 180, 1620, 550), "Shared BM25 first stage\nTop 50 candidates", "#DCEAF7"),
        ((1880, 180, 2510, 550), "Six fixed paths\nP0-P5", "#D8F0EC"),
        ((2770, 180, 3400, 550), "720 path outputs\n10,385 evidence labels", "#F8EBC7"),
    ]
    for xy, text, fill in boxes:
        _box(draw, xy, text, fill)
    arrows = [
        ((730, 365), (990, 365)),
        ((1620, 365), (1880, 365)),
        ((2510, 365), (2770, 365)),
    ]
    for start, end in arrows:
        _arrow(draw, start, end)

    lower = [
        ((360, 820, 1120, 1190), "Path diagnostics\nCompleteness | Harm | Cost", "#E7EEF5"),
        ((1420, 820, 2180, 1190), "Lightweight routing\nLR | XGBoost | Heuristic", "#E2F1EE"),
        (
            (2480, 820, 3240, 1190),
            "Calibration-only abstention\nFrozen risk-coverage rule",
            "#F8E7E7",
        ),
    ]
    for xy, text, fill in lower:
        _box(draw, xy, text, fill)
    for end in ((740, 820), (1800, 820), (2860, 820)):
        _arrow(draw, (3085, 550), end, color="#5C7080", width=5)

    footer = (
        "Question-grouped five-fold evaluation  |  paired 10,000-resample intervals  |  "
        "prespecified NO-GO gate"
    )
    font = _font(32)
    bbox = draw.textbbox((0, 0), footer, font=font)
    draw.text(((3600 - (bbox[2] - bbox[0])) / 2, 1370), footer, font=font, fill=INK)
    image.save(OUT / "figure0_study_design.png", dpi=(300, 300))


def outcome_definition() -> None:
    image = Image.new("RGB", (3150, 1380), "white")
    draw = ImageDraw.Draw(image)
    title = "Risk-sensitive path endpoint"
    font = _font(48, bold=True)
    bbox = draw.textbbox((0, 0), title, font=font)
    draw.text(((3150 - (bbox[2] - bbox[0])) / 2, 90), title, font=font, fill=INK)
    _box(
        draw,
        (150, 300, 1320, 680),
        "Complete evidence\nAll REQUIRED items or one SUFFICIENT item",
        "#D8F0EC",
        34,
    )
    _box(
        draw,
        (1830, 300, 3000, 680),
        "No harmful expansion\nNo materially misleading item or sidecar",
        "#F8EBC7",
        34,
    )
    _box(
        draw,
        (900, 870, 2250, 1240),
        "Combined path success\nCompleteness AND zero HARMFUL evidence",
        "#DCEAF7",
        38,
    )
    _arrow(draw, (735, 680), (1250, 870), color="#2A9D8F", width=8)
    _arrow(draw, (2415, 680), (1900, 870), color="#C69A24", width=8)
    image.save(OUT / "figure3_outcome_definition.png", dpi=(300, 300))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    study_design()
    outcome_definition()
