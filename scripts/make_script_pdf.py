"""Print-ready pitch script. Key phrases are bold, with a time cue for each slide.

    python scripts/make_script_pdf.py
"""
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from pitch import SCRIPT, plain

REP = Path(__file__).resolve().parents[1] / "docs" / "reports"
WPM = 150
GREEN = colors.HexColor("#0e7f73")
title = ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=GREEN)
sub = ParagraphStyle("S", fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#444444"), spaceAfter=10)
head = ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=GREEN, spaceBefore=9, spaceAfter=2)
body = ParagraphStyle("B", fontName="Helvetica", fontSize=14, leading=20)

total = sum(len(plain(t).split()) for _, t in SCRIPT)
assert total <= 450, f"script runs over three minutes at {total} words"
story = [Paragraph("KASCO three-minute pitch script", title), Paragraph(f"Wee Zhern Ray. Autonomous SG 2026, Airbus Challenge 3. {total} words, about {total / WPM * 60:.0f} seconds at {WPM} words a minute. Bold marks the phrases to stress.", sub)]
clock = 0.0
for n, (name, text) in enumerate(SCRIPT, 1):
    words = len(plain(text).split())
    start = clock
    clock += words / WPM * 60
    stamp = f"{int(start // 60)}:{int(start % 60):02d}"
    marked = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    story.append(KeepTogether([Paragraph(f"Slide {n}: {name} &nbsp;&nbsp; start {stamp}", head), Paragraph(marked, body)]))
story.append(Spacer(1, 6))
doc = SimpleDocTemplate(str(REP / "KASCO_Pitch_Script.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.5 * cm, title="KASCO pitch script", author="Wee Zhern Ray")
doc.build(story)
print("script words", total, "seconds", round(total / WPM * 60))
