"""Pillow-based rendering of the three carousel slides."""
import os

from PIL import Image, ImageDraw, ImageFont

from .config import BG, FG, HANDLE, HEADER, IMG_H, IMG_W, OUT_DIR

FONT_DIR = OUT_DIR.parent / "fonts"
FONT_CANDIDATES = [
    str(FONT_DIR / "Anton-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default(size)


def wrap_text(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def render_slide(text, path, with_header=True):
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)
    text = capitalize_first(text.strip())

    # header (question slide only)
    if with_header:
        draw.text((IMG_W // 2, 90), HEADER, font=load_font(64), fill=FG, anchor="ma")

    # main text, auto-fit and centered
    box_w = IMG_W - 160
    box_top = 210 if with_header else 140
    box_bottom = IMG_H - 190
    box_h = box_bottom - box_top
    size = 150
    while size > 30:
        font = load_font(size)
        lines = wrap_text(draw, text, font, box_w)
        if size * 1.2 * len(lines) <= box_h:
            break
        size -= 4
    font = load_font(size)
    lines = wrap_text(draw, text, font, box_w)
    total_h = size * 1.2 * len(lines)
    y = box_top + (box_h - total_h) / 2
    for line in lines:
        draw.text((IMG_W // 2, y), line, font=font, fill=FG, anchor="ma")
        y += size * 1.2

    # bottom-right handle
    draw.text((IMG_W - 60, IMG_H - 60), HANDLE, font=load_font(40), fill=FG, anchor="rs")

    img.save(path, "JPEG", quality=92)
    return path


def render_images(question, short_answer, long_answer, draft_id):
    """Render slides to out/<draft_id>/ and return repo-relative paths."""
    d = OUT_DIR / draft_id
    d.mkdir(parents=True, exist_ok=True)
    render_slide(question, str(d / "0.jpg"), with_header=True)
    render_slide(short_answer, str(d / "1.jpg"), with_header=False)
    render_slide(long_answer, str(d / "2.jpg"), with_header=False)
    return [f"out/{draft_id}/0.jpg", f"out/{draft_id}/1.jpg", f"out/{draft_id}/2.jpg"]
