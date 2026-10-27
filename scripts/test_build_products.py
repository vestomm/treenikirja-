"""Testit tuotelistan rakentamiselle. Aja: python -m unittest discover -s scripts"""

import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import build_products as bp  # noqa: E402

HEADER = [
    "code", "url", "product_name", "generic_name", "brands", "countries_tags", "serving_quantity",
    "additives_n", "nutriscore_grade", "nova_group", "energy-kj_100g", "energy-kcal_100g", "energy_100g",
    "fat_100g", "carbohydrates_100g", "proteins_100g",
]


def tsv(rows):
    """Rivit OFF:n vientimuodossa (sarkaimet, ei lainausmerkkejä)."""
    lines = ["\t".join(HEADER)]
    for r in rows:
        lines.append("\t".join(str(r.get(h, "")) for h in HEADER))
    return "\n".join(lines) + "\n"


FI = "en:finland,en:sweden"
RAHKA = {"code": "6408430000135", "product_name": "Maustamaton rahka", "brands": "Valio, Valio Oy", "countries_tags": FI,
         "energy-kcal_100g": "63", "proteins_100g": "11.5", "carbohydrates_100g": "3.6", "fat_100g": "0.2",
         "nova_group": "1", "nutriscore_grade": "a", "additives_n": "0", "serving_quantity": "250"}


class ParseRow(unittest.TestCase):
    def test_kelvollinen_suomalainen_tuote(self):
        self.assertEqual(bp.parse_row(RAHKA), ["6408430000135", "Maustamaton rahka", "Valio", 63, 11.5, 3.6, 0.2, 1, "a", 0, 250.0])

    def test_muu_maa_ohitetaan(self):
        self.assertIsNone(bp.parse_row({**RAHKA, "countries_tags": "en:france"}))

    def test_tagi_tarkistetaan_kokonaisena(self):
        self.assertIsNone(bp.parse_row({**RAHKA, "countries_tags": "en:finlandia-fake"}))

    def test_kcal_kilojouleista(self):
        r = bp.parse_row({**RAHKA, "energy-kcal_100g": "", "energy-kj_100g": "1000"})
        self.assertEqual(r[3], 239)
        r = bp.parse_row({**RAHKA, "energy-kcal_100g": "", "energy_100g": "418.4"})
        self.assertEqual(r[3], 100)

    def test_puuttuvat_makrot_ohitetaan(self):
        self.assertIsNone(bp.parse_row({**RAHKA, "fat_100g": ""}))
        self.assertIsNone(bp.parse_row({**RAHKA, "energy-kcal_100g": ""}))

    def test_mahdottomat_arvot_ohitetaan(self):
        self.assertIsNone(bp.parse_row({**RAHKA, "proteins_100g": "80", "carbohydrates_100g": "40"}))
        self.assertIsNone(bp.parse_row({**RAHKA, "energy-kcal_100g": "3000"}))
        self.assertIsNone(bp.parse_row({**RAHKA, "fat_100g": "-1"}))
        self.assertIsNone(bp.parse_row({**RAHKA, "fat_100g": "nan"}))

    def test_virheellinen_koodi_tai_nimi(self):
        self.assertIsNone(bp.parse_row({**RAHKA, "code": "123"}))
        self.assertIsNone(bp.parse_row({**RAHKA, "code": "abc12345"}))
        self.assertIsNone(bp.parse_row({**RAHKA, "product_name": "  "}))

    def test_nimi_varalla_generic_name(self):
        self.assertEqual(bp.parse_row({**RAHKA, "product_name": "", "generic_name": "Rahka"})[1], "Rahka")

    def test_valinnaiset_kentat_siivotaan(self):
        r = bp.parse_row({**RAHKA, "nova_group": "7", "nutriscore_grade": "unknown", "additives_n": "", "serving_quantity": "0"})
        self.assertEqual(r[7:], [None, None, None, None])

    def test_pilkku_desimaalina(self):
        self.assertEqual(bp.parse_row({**RAHKA, "proteins_100g": "11,5"})[4], 11.5)


class Build(unittest.TestCase):
    def test_suodatus_tilastot_ja_tuplat(self):
        text = tsv([
            RAHKA,
            {**RAHKA, "code": "3017624010701", "product_name": "Nutella", "countries_tags": "en:france"},
            {**RAHKA, "product_name": "Rahka uusi nimi"},  # sama koodi → viimeisin jää
            {**RAHKA, "code": "96385074", "product_name": 'Patukka "Max" 50 g', "fat_100g": ""},  # ei rasvaa
            {**RAHKA, "code": "4006381333931", "product_name": 'Kaura "Extra"'},  # lainausmerkki nimessä
        ])
        rows, stats = bp.build(io.StringIO(text))
        self.assertEqual(stats, {"rows": 5, "finland": 4, "kept": 2})
        self.assertEqual([r[0] for r in rows], ["4006381333931", "6408430000135"])
        self.assertEqual(rows[1][1], "Rahka uusi nimi")
        self.assertEqual(rows[0][1], 'Kaura "Extra"')

    def test_muuttuneet_sarakkeet_pysayttavat(self):
        with self.assertRaises(SystemExit) as cm:
            bp.build(io.StringIO("code\tproduct_name\n123\tx\n"))
        self.assertIn("Puuttuu", str(cm.exception))

    def test_js_tiedosto_on_kelvollinen(self):
        rows, _ = bp.build(io.StringIO(tsv([RAHKA])))
        js = bp.to_js(rows, "2026-10-27")
        self.assertTrue(js.startswith("/* Tiedot: Open Food Facts"))
        body = js.split("window.TK_PRODUCTS=", 1)[1].rstrip(";\n")
        data = json.loads(body)
        self.assertEqual(data["fields"], bp.FIELDS)
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["rows"][0]), len(bp.FIELDS))


class Cli(unittest.TestCase):
    def test_koko_ajo_paikallisella_gz_tiedostolla(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "vienti.csv.gz")
            with gzip.open(src, "wt", encoding="utf-8") as f:
                f.write(tsv([RAHKA, {**RAHKA, "code": "4006381333931"}]))
            out = os.path.join(d, "products-fi.js")
            script = os.path.join(os.path.dirname(__file__), "build_products.py")
            ok = subprocess.run([sys.executable, script, "--source", src, "--out", out, "--min-count", "1"], capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("listalle 2", ok.stdout)
            self.assertTrue(os.path.exists(out))
            # Sama data uudelleen → tiedostoa ei kosketa (päiväys ei saa aiheuttaa turhaa muutosta)
            with open(out, "r+", encoding="utf-8") as f:
                content = f.read().replace(bp.datetime.now(bp.timezone.utc).strftime("%Y-%m-%d"), "2000-01-01")
                f.seek(0); f.write(content); f.truncate()
            again = subprocess.run([sys.executable, script, "--source", src, "--out", out, "--min-count", "1"], capture_output=True, text=True)
            self.assertIn("Ei muutoksia", again.stdout)
            with open(out, encoding="utf-8") as f:
                self.assertIn("2000-01-01", f.read())
            # Liian vähän tuotteita → virhe eikä tiedostoa korvata
            os.remove(out)
            bad = subprocess.run([sys.executable, script, "--source", src, "--out", out, "--min-count", "100"], capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
