"""Prepare slide 1 assets from the user's supplied images.

Logos are cut from the official event poster, so none are redrawn. The background comes
from the KASCO cover reference: baked-in text is filled with its own scenery, and the
aircraft's generated livery is removed, leaving a generic aircraft.

    python scripts/make_brand_assets.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "branding"
OUT = ROOT / "docs" / "reports" / "fig" / "brand"
OUT.mkdir(parents=True, exist_ok=True)
NAVY = np.array([10, 22, 38], dtype=float)

LOGOS = {
    "acacia": (132, 12, 260, 58),
    "product_club": (312, 10, 455, 63),
    "claude": (227, 218, 361, 253),
    "airbus": (60, 302, 206, 334),
    "five_degrees": (236, 297, 428, 330),
    "nus_hackers": (452, 289, 578, 336),
}


def key_dark(rgb: np.ndarray, low: float, high: float) -> Image.Image:
    """Turns a dark backdrop transparent, keeping the bright logo."""
    level = rgb.max(axis=2)
    alpha = np.clip((level - low) / (high - low), 0, 1)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def logos() -> None:
    poster = Image.open(SRC / "event_poster.png").convert("RGB")
    for name, box in LOGOS.items():
        crop = poster.crop(box)
        big = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
        im = key_dark(np.asarray(big, dtype=float), 48, 120)
        if name == "product_club":
            # Monochrome logo with faint line art, so it is shown in solid white.
            # The mark needs a lower key than the name beside it, which would otherwise clog.
            a = np.asarray(key_dark(np.asarray(big, dtype=float), 80, 175).getchannel("A")).copy()
            a[:, :215] = np.asarray(key_dark(np.asarray(big, dtype=float), 26, 84).getchannel("A"))[:, :215]
            a = Image.fromarray(a)
            im = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im.putalpha(a)
        if name == "nus_hackers":
            # The badge is a black disc, so it stays solid inside the keyed logo.
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).ellipse((12, 8, 12 + 180, 8 + 180), fill=255)
            a = np.maximum(np.asarray(im.getchannel("A")), np.asarray(mask))
            im.putalpha(Image.fromarray(a))
        im.crop(im.getbbox()).save(OUT / f"logo_{name}.png")


def tile(src: np.ndarray, h: int, w: int) -> np.ndarray:
    """Covers an area by repeating a patch with alternating flips, so no seams show."""
    rows = []
    for r in range(h // src.shape[0] + 1):
        row = []
        for c in range(w // src.shape[1] + 1):
            p = src
            if c % 2:
                p = p[:, ::-1]
            if r % 2:
                p = p[::-1]
            row.append(p)
        rows.append(np.hstack(row))
    return np.vstack(rows)[:h, :w]


def diffuse(a: np.ndarray, mask: np.ndarray, steps: int = 300) -> np.ndarray:
    """Fills masked pixels from their surroundings."""
    a = a.copy()
    for _ in range(steps):
        n = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4
        a[mask] = n[mask]
    return a


def background() -> None:
    im = np.asarray(Image.open(SRC / "kasco_cover_reference.jpg").convert("RGB"), dtype=float).copy()
    H, W, _ = im.shape

    # Remove generated lettering from the fuselage.
    x0, y0, x1, y1 = 1218, 280, 1290, 362
    box = im[y0:y1, x0:x1]
    blue = (box[..., 2] > box[..., 0] + 12) & (box.mean(axis=2) < 170)
    grown = np.asarray(Image.fromarray((blue * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    im[y0:y1, x0:x1] = diffuse(box, grown)

    # Smooth the tail so no generated mark remains.
    tail = Image.fromarray(im.astype(np.uint8))
    soft = tail.filter(ImageFilter.GaussianBlur(9))
    mask = Image.new("L", tail.size, 0)
    ImageDraw.Draw(mask).polygon([(1418, 383), (1458, 297), (1466, 301), (1441, 383)], fill=255)
    tail.paste(soft, (0, 0), mask.filter(ImageFilter.GaussianBlur(1.5)))
    im = np.asarray(tail, dtype=float).copy()

    # Cover all baked-in text with scenery from text-free parts of the same picture.
    # The forest patch is enlarged and softened so it repeats less and sits back behind text.
    patch = Image.fromarray(im[250:440, 775:930].astype(np.uint8))
    patch = patch.resize((patch.width * 5 // 2, patch.height * 5 // 2), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))
    forest = tile(np.asarray(patch, dtype=float), H, W)
    sky = np.zeros((H, W, 3))
    sky[120:236] = tile(im[120:236, 720:960], 116, W)
    sky[:120] = sky[120]
    sky[236:] = sky[235]
    t = np.clip((np.arange(H) - 222) / 28, 0, 1)[:, None, None]
    fill = t * forest + (1 - t) * sky

    keep = np.full((H, W), 255, dtype=np.uint8)
    keep[120:236, :760] = 0
    keep[236:440, :800] = 0
    keep[425:520, :1035] = 0
    keep[505:795, :905] = 0
    keep[505:795, 1000:1650] = 0
    keep[795:] = 0
    blend = Image.fromarray(keep).filter(ImageFilter.GaussianBlur(14))
    fade = (np.asarray(blend, dtype=float) / 255)[..., None]
    clean = fade * im + (1 - fade) * fill

    # Dark top band for the logos, and a navy wash for text legibility on the left.
    s = np.clip((np.arange(H) - 100) / 90, 0, 1)
    top = (1 - s * s * (3 - 2 * s))[:, None, None]
    clean = top * NAVY + (1 - top) * clean
    wash = 0.74 * np.clip(1 - np.arange(W) / (0.62 * W), 0, 1)[None, :, None]
    clean = wash * NAVY + (1 - wash) * clean
    base = np.clip((np.arange(H) - 790) / 60, 0, 1)[:, None, None] * 0.7
    clean = base * NAVY + (1 - base) * clean
    Image.fromarray(clean.astype(np.uint8)).resize((1920, 1080), Image.LANCZOS).save(OUT / "cover_bg.jpg", quality=88)


def elements() -> None:
    src = np.asarray(Image.open(SRC / "kasco_cover_reference.jpg").convert("RGB"), dtype=float)
    key_dark(src[262:436, 55:778], 135, 190).save(OUT / "wordmark.png")
    for n, cx in enumerate((120, 333, 558, 792)):
        crop = src[600:712, cx - 56:cx + 56]
        key_dark(crop, 120, 190).resize((336, 336), Image.LANCZOS).save(OUT / f"flow_{n}.png")
    for n, cx in enumerate((91, 487, 872, 1321)):
        crop = src[828:892, cx - 32:cx + 32]
        key_dark(crop, 120, 190).resize((256, 256), Image.LANCZOS).save(OUT / f"band_{n}.png")


if __name__ == "__main__":
    logos()
    background()
    elements()
    print("brand assets in", OUT)
