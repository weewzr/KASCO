"""Build the KASCO submission cover from the real solver map.

    python scripts/make_cover.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "docs" / "reports"
FONTS = Path("C:/Windows/Fonts")
NAVY, TEAL, WHITE, MUTED = (10, 22, 38), (25, 181, 165), (255, 255, 255), (207, 219, 227)
W, H = 1920, 1080


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


img = Image.new("RGB", (W, H), NAVY)
m = Image.open(REP / "fig" / "map_clean_dark.png").convert("RGB")
m = m.crop(m.getbbox() if False else (120, 40, m.width - 120, m.height - 40))
scale = 1000 / m.height
m = m.resize((int(m.width * scale), 1000), Image.LANCZOS)
img.paste(m, (W - m.width, 40))
d = ImageDraw.Draw(img)
d.text((80, 90), "AUTONOMOUS SG HACKATHON 2026  |  AIRBUS CHALLENGE #3", font=font("segoeuib.ttf", 28), fill=TEAL)
d.text((74, 180), "KASCO", font=font("segoeuib.ttf", 210), fill=WHITE)
d.text((80, 470), "Kalimantan SAF Supply", font=font("segoeuib.ttf", 66), fill=WHITE)
d.text((80, 552), "Chain Optimiser", font=font("segoeuib.ttf", 66), fill=WHITE)
d.text((80, 668), "AI-Driven Optimisation for a More", font=font("segoeui.ttf", 40), fill=MUTED)
d.text((80, 720), "Sustainable Aviation Future", font=font("segoeui.ttf", 40), fill=MUTED)
d.text((80, 815), "Wee Zhern Ray", font=font("segoeuib.ttf", 34), fill=TEAL)
d.text((80, 925), "Acacia Hackathon Society    NUS Product Club    Airbus", font=font("segoeuib.ttf", 26), fill=WHITE)
d.text((80, 965), "Five Degrees    NUS Hackers    National University of Singapore", font=font("segoeuib.ttf", 26), fill=WHITE)
d.text((80, 1012), "Map: solved KASCO base case on a Natural Earth coastline. Organisations named for event context.", font=font("segoeui.ttf", 20), fill=MUTED)
out = REP / "KASCO_Cover.jpg"
img.save(out, "JPEG", quality=88, optimize=True)
print(out, round(out.stat().st_size / 1e6, 2), "MB")
