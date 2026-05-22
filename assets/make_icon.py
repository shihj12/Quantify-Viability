"""Generate assets/icon.ico — a green (live) + red (dead) dot motif.

    python assets/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(1, size // 16)
    draw.rounded_rectangle([pad, pad, size - pad, size - pad],
                           radius=size // 6, fill=(38, 40, 46, 255))
    r = size * 0.27
    for (cx, cy), colour in (((0.40, 0.40), (60, 210, 90, 255)),
                             ((0.63, 0.63), (232, 72, 96, 235))):
        x, y = cx * size, cy * size
        draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
    return img


def main() -> None:
    out = Path(__file__).with_name("icon.ico")
    master = render(256)
    master.save(out, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
