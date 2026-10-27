"""Rakentaa Treenikirjan tuotelistan Open Food Factsin CSV-viennistä.

Lataa koko viennin virtana (noin 1 Gt pakattuna), poimii Suomessa myytävät tuotteet,
joilla on täydet ravintoarvot, ja kirjoittaa ne pieneen JavaScript-tiedostoon:

    window.TK_PRODUCTS = {v: 1, updated: "...", count: N, fields: [...], rows: [[...], ...]};

Treenikirja lataa tiedoston jsDelivrin kautta <script>-tagilla, koska artefaktisivu
ei saa hakea dataa suoraan Open Food Factsista.

Käyttö:
    python scripts/build_products.py --out products-fi.js
    python scripts/build_products.py --source testi.csv.gz --out /tmp/x.js   # paikallinen tiedosto

Tiedot: Open Food Facts (https://openfoodfacts.org), lisenssi ODbL.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

EXPORT_URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
# Open Food Facts pyytää jokaiseen pyyntöön oman User-Agentin.
USER_AGENT = "Treenikirja/1.0 (https://github.com/vestomm/treenikirja-)"
COUNTRY_TAG = "en:finland"
NEARBY_TAGS = {"en:sweden", "en:norway", "en:denmark", "en:estonia"}  # tilastoa varten: laajennuksen koko

# Kentät tiedostossa, tässä järjestyksessä. Sovellus lukee ne samassa järjestyksessä.
FIELDS = ["code", "name", "brand", "kcal", "protein", "carbs", "fat", "nova", "nutriscore", "additives", "serving"]

REQUIRED_COLUMNS = ["code", "product_name", "brands", "countries_tags", "proteins_100g", "carbohydrates_100g", "fat_100g"]
ENERGY_COLUMNS = ["energy-kcal_100g", "energy-kj_100g", "energy_100g"]


def num(value: str | None) -> float | None:
    """Luku tekstistä. Tyhjä, ei-numero, NaN tai negatiivinen → None."""
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    if not value:
        return None
    try:
        n = float(value)
    except ValueError:
        return None
    if math.isnan(n) or math.isinf(n) or n < 0:
        return None
    return n


def kcal_from(row: dict) -> float | None:
    """Energia kcal/100 g. Jos kcal puuttuu, lasketaan kilojouleista (1 kcal = 4,184 kJ)."""
    kcal = num(row.get("energy-kcal_100g"))
    if kcal is not None:
        return kcal
    kj = num(row.get("energy-kj_100g"))
    if kj is None:
        kj = num(row.get("energy_100g"))  # OFF:n energy_100g on kilojouleina
    return kj / 4.184 if kj is not None else None


def clean_text(value: str | None, limit: int) -> str:
    return " ".join((value or "").split())[:limit]


def first_brand(value: str | None) -> str:
    return clean_text((value or "").split(",")[0], 60)


def country_tags(row: dict) -> set[str]:
    return {t.strip() for t in (row.get("countries_tags") or "").split(",") if t.strip()}


def parse_row(row: dict, check_country: bool = True) -> list | None:
    """Yksi CSV-rivi → tiedoston rivi, tai None jos tuote ei kelpaa."""
    if check_country and COUNTRY_TAG not in country_tags(row):
        return None
    code = (row.get("code") or "").strip()
    if not code.isdigit() or not 8 <= len(code) <= 14:
        return None
    name = clean_text(row.get("product_name_fi") or row.get("product_name") or row.get("generic_name"), 100)
    if not name:
        return None

    kcal = kcal_from(row)
    protein = num(row.get("proteins_100g"))
    carbs = num(row.get("carbohydrates_100g"))
    fat = num(row.get("fat_100g"))
    if None in (kcal, protein, carbs, fat):
        return None
    # Samat järkevyystarkistukset kuin sovelluksessa: 100 g:ssa ei voi olla yli 100 g makroja.
    if protein + carbs + fat > 100.5 or kcal > 950:
        return None

    nova = num(row.get("nova_group"))
    nova = int(nova) if nova is not None and nova in (1, 2, 3, 4) else None
    grade = (row.get("nutriscore_grade") or "").strip().lower()
    grade = grade if grade in ("a", "b", "c", "d", "e") else None
    additives = num(row.get("additives_n"))
    additives = int(additives) if additives is not None and additives == int(additives) else None
    serving = num(row.get("serving_quantity"))
    serving = round(serving, 1) if serving is not None and 0 < serving <= 5000 else None

    return [
        code,
        name,
        first_brand(row.get("brands")),
        round(kcal),
        round(protein, 1),
        round(carbs, 1),
        round(fat, 1),
        nova,
        grade,
        additives,
        serving,
    ]


def open_source(source: str):
    """Avaa viennin tekstivirtana: URL tai paikallinen .csv.gz / .csv."""
    if source.startswith("http"):
        req = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        raw = urllib.request.urlopen(req, timeout=120)
    else:
        raw = open(source, "rb")
    if source.endswith(".gz"):
        raw = gzip.GzipFile(fileobj=raw)
    return io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")


def build(lines) -> tuple[list[list], dict]:
    """Lukee sarkaimin erotellun viennin ja palauttaa (rivit, tilastot)."""
    csv.field_size_limit(sys.maxsize)
    # OFF:n vienti on sarkaimin eroteltu ilman lainausmerkkejä; QUOTE_NONE estää
    # tuotenimissä olevia "-merkkejä sotkemasta rivejä.
    reader = csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE)
    header = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing or not any(c in header for c in ENERGY_COLUMNS):
        similar = [h for h in header if any(k in h for k in ("energy", "protein", "carbo", "fat", "countr", "name", "brand"))]
        raise SystemExit(f"Viennin sarakkeet ovat muuttuneet. Puuttuu: {missing or ENERGY_COLUMNS}. Lähimmät: {similar[:40]}")

    stats = {"rows": 0, "finland": 0, "kept": 0, "fi_prefix_untagged_complete": 0, "nearby_complete": 0}
    by_code: dict[str, list] = {}
    for row in reader:
        stats["rows"] += 1
        tags = country_tags(row)
        if COUNTRY_TAG in tags:
            stats["finland"] += 1
            parsed = parse_row(row, check_country=False)
            if parsed:
                by_code[parsed[0]] = parsed  # sama koodi kahdesti → viimeisin jää
        else:
            # Pelkkä tilasto: paljonko lista kasvaisi laajennuksilla (ei mukana tiedostossa).
            code = (row.get("code") or "").strip()
            if code.startswith("64") or tags & NEARBY_TAGS:
                if parse_row(row, check_country=False):
                    if code.startswith("64"):
                        stats["fi_prefix_untagged_complete"] += 1
                    if tags & NEARBY_TAGS:
                        stats["nearby_complete"] += 1
        if stats["rows"] % 500_000 == 0:
            print(f"  {stats['rows']:,} riviä, Suomen tuotteita {stats['finland']:,}", flush=True)
    rows = sorted(by_code.values(), key=lambda r: r[0])  # vakaa järjestys → pienet muutokset gitissä
    stats["kept"] = len(rows)
    return rows, stats


def to_js(rows: list[list], updated: str, stats: dict | None = None) -> str:
    payload = {"v": 1, "updated": updated, "count": len(rows), "source": "Open Food Facts (ODbL)", "stats": stats or {}, "fields": FIELDS, "rows": rows}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return "/* Tiedot: Open Food Facts (https://openfoodfacts.org), ODbL. Generoitu automaattisesti. */\nwindow.TK_PRODUCTS=" + body + ";\n"


def read_previous(path: str) -> tuple | None:
    """Aiemman tiedoston (rivit, tilastot) vertailua varten. Puuttuva tai rikkinäinen → None."""
    try:
        with open(path, encoding="utf-8") as f:
            body = f.read().split("window.TK_PRODUCTS=", 1)[1].rstrip().rstrip(";")
        data = json.loads(body)
        return data["rows"], data.get("stats")
    except (OSError, IndexError, ValueError, KeyError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", default=EXPORT_URL, help="Viennin URL tai paikallinen tiedosto")
    ap.add_argument("--out", default="products-fi.js")
    ap.add_argument("--min-count", type=int, default=100, help="Alle tämän → virhe, vanha lista säilyy")
    args = ap.parse_args()

    print(f"Luetaan {args.source}", flush=True)
    with open_source(args.source) as lines:
        rows, stats = build(lines)
    print(f"Valmis: {stats['rows']:,} riviä, Suomen tuotteita {stats['finland']:,}, listalle {stats['kept']:,}")
    print(f"  Laajennukset: 64-koodi ilman Suomi-merkintää {stats['fi_prefix_untagged_complete']:,}, lähimaat {stats['nearby_complete']:,}")

    if stats["kept"] < args.min_count:
        raise SystemExit(f"Vain {stats['kept']} tuotetta, oletettiin vähintään {args.min_count}. Vanhaa listaa ei korvata.")

    if read_previous(args.out) == (rows, stats):
        print(f"Ei muutoksia tuotteisiin, {args.out} jätetään ennalleen.")
        return

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    js = to_js(rows, updated, stats)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(js)
    size_mb = len(js.encode("utf-8")) / 1e6
    print(f"Kirjoitettu {args.out} ({size_mb:.1f} Mt)")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(
                f"### Tuotelista {updated}\n\n| | |\n|---|---|\n"
                f"| Viennin rivejä | {stats['rows']:,} |\n| Suomessa myytäviä | {stats['finland']:,} |\n"
                f"| Listalla (täydet ravintoarvot) | {stats['kept']:,} |\n| Tiedoston koko | {size_mb:.1f} Mt |\n"
            )


if __name__ == "__main__":
    main()
