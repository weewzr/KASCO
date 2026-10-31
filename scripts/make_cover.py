"""Build the KASCO submission cover from slide 1 of the exported deck.

Run after scripts/export_deck.ps1, so the cover always matches the slide.

    python scripts/make_cover.py
"""
from pathlib import Path

import pymupdf
from PIL import Image

REP = Path(__file__).resolve().parents[1] / "docs" / "reports"
W, H = 1920, 1080

page = pymupdf.open(REP / "KASCO_Pitch.pdf")[0]
pix = page.get_pixmap(matrix=pymupdf.Matrix(W / page.rect.width, H / page.rect.height), alpha=False)
out = REP / "KASCO_Cover.jpg"
Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(out, "JPEG", quality=90, optimize=True)
print(out, pix.width, pix.height, round(out.stat().st_size / 1e6, 2), "MB")
