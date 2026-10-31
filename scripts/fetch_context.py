"""Fetches the public figures behind the real-uplift reality check and derives the estimate.

These figures appear only in a labelled reality-check scenario. They never touch the
official base case. Each source page is fetched and the quoted figure is searched for,
so the record shows which values were confirmed by this script.

    python scripts/fetch_context.py
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JET_T_PER_KL = 0.80
AGENT = {"User-Agent": "Mozilla/5.0 (compatible; airbustrack3ray-context/1.0)"}

SOURCES = [
    ("pax_PNK", 2387536, "passengers 2024", "2,387,536", ["https://en.wikipedia.org/wiki/Supadio_International_Airport"]),
    ("pax_PKN", 472637, "passengers 2024", "472,637", ["https://en.wikipedia.org/wiki/Iskandar_Airport"]),
    ("pax_BPN", 5534519, "passengers 2024", "5,534,519", ["https://en.wikipedia.org/wiki/Sultan_Aji_Muhammad_Sulaiman_Sepinggan_Airport"]),
    ("pax_TRK", 651557, "passengers 2024", "651,557", ["https://en.wikipedia.org/wiki/Juwata_Airport"]),
    ("avtur_PNK", 77.0, "kL per day, West Kalimantan normal daily distribution, April 2024", "77 Kiloliter", ["https://pontianakpost.jawapos.com/pro-bisnis/1464533107/permintaan-avtur-naik-8-di-bandara-supadio-pertamina-pastikan-stok-bahan-bakar-pesawat-udara-aman"]),
    ("avtur_BPN", 222.0, "kL per day, Balikpapan, 2024 Pertamina statement via regional press", "222 KL", ["https://ikn.kompas.com/read/2024/03/25/071604087/pertamina-pastikan-stok-bbm-lpg-serta-avtur-di-kalimantan-timur-aman"]),
]


def fetch(url):
    req = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


rows = []
for key, value, what, needle, urls in SOURCES:
    row = {"key": key, "value": value, "what": what, "url": urls[0], "fetched": False, "figure_found": False}
    for url in urls:
        try:
            page = fetch(url)
            row.update(url=url, fetched=True, figure_found=needle in page)
            break
        except Exception as e:
            row["error"] = str(e)[:80]
    rows.append(row)
    print(row["key"], "fetched", row["fetched"], "found", row["figure_found"], flush=True)
    time.sleep(1)

v = {r["key"]: r["value"] for r in rows}
kl = {"PNK": v["avtur_PNK"] * 365, "BPN": v["avtur_BPN"] * 365}
lpp = (kl["PNK"] + kl["BPN"]) * 1000 / (v["pax_PNK"] + v["pax_BPN"])
kl["PKN"] = v["pax_PKN"] * lpp / 1000
kl["TRK"] = v["pax_TRK"] * lpp / 1000
uplift = {a: round(kl[a] * JET_T_PER_KL / 1000, 2) for a in ("PNK", "PKN", "BPN", "TRK")}
(ROOT / "data" / "real_uplift.csv").write_text("iata,uplift_kt\n" + "".join(f"{a},{u}\n" for a, u in uplift.items()))
out = {"date": time.strftime("%Y-%m-%d"), "jet_t_per_kl": JET_T_PER_KL, "litres_per_passenger": round(lpp, 2), "uplift_kt": uplift, "total_kt": round(sum(uplift.values()), 1), "note": "Reality check only. PKN and TRK are scaled from passengers. The PNK volume is reported for West Kalimantan as a whole.", "sources": rows}
(ROOT / "docs" / "data" / "context_check.json").write_text(json.dumps(out, indent=1))
print(uplift, "L/pax", round(lpp, 2))
