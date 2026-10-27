# Treenikirja: tuotelista

Suomessa myytävien elintarvikkeiden ravintoarvot Treenikirja-sovelluksen viivakoodi- ja nimihakua varten.

## Miten tämä toimii

1. GitHub Actions ajaa maanantaisin skriptin `scripts/build_products.py`.
2. Skripti lataa Open Food Factsin koko CSV-viennin ja poimii tuotteet, joilla on täydet ravintoarvot (energia, proteiini, hiilihydraatit, rasva per 100 g) ja jotka
   - on merkitty Suomessa myytäviksi tai joilla on suomalainen 64-alkuinen viivakoodi (`fi: 1`), tai
   - myydään Ruotsissa, Norjassa, Tanskassa tai Virossa (`fi: 0`). Moni tuontituote myydään Suomessa samalla viivakoodilla.
3. Tulos tallentuu tiedostoon `products-fi.js`, jos se muuttui.
4. Treenikirja-sovellukseen lista viedään sovelluksen omaksi tiedostoksi `products-fi.json`
   (skripti `sync_products.py` sovelluksen lähdekoodissa) ja julkaistaan sovelluksen mukana.

   Huom: Claude-artefakti ei saa ladata tiedostoja jsDelivrin GitHub-polusta (`cdn.jsdelivr.net/gh/...`),
   vain npm-paketteja. Siksi listaa ei ladata suoraan tästä reposta, vaan se kopioidaan sovellukseen.
   Uusi lista päätyy sovellukseen, kun sovellus julkaistaan uudelleen.

Repossa on vain julkista tuotedataa. Treenit ja ruokapäiväkirja eivät tule tänne.

## Käsin ajo

GitHubissa: **Actions → Päivitä tuotelista → Run workflow**. Ajo kestää noin 10–20 minuuttia, ja yhteenveto näyttää tuotemäärät.

Paikallisesti:

```bash
python -m unittest discover -s scripts      # testit
python scripts/build_products.py --out products-fi.js
```

## Tiedoston muoto

```js
window.TK_PRODUCTS = {
  v: 1, updated: "2026-10-27", count: 12345, source: "Open Food Facts (ODbL)",
  stats: { rows: 2117569, finland: 3386, kept: 12000, kept_fi: 3500, kept_near: 8500 },
  fields: ["code", "name", "brand", "kcal", "protein", "carbs", "fat", "nova", "nutriscore", "additives", "serving", "fi"],
  rows: [["6408430000135", "Maustamaton rahka", "Valio", 63, 11.5, 3.6, 0.2, 1, "a", 0, 250, 1], ...]
};
```

Arvot ovat per 100 g. `nova`, `nutriscore`, `additives` ja `serving` voivat olla `null`.

## Lisenssi ja lähde

Tuotetiedot: [Open Food Facts](https://world.openfoodfacts.org), lisensoitu [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/) -lisenssillä. Yksittäisten tuotteiden sisältö: [Database Contents License](https://opendatacommons.org/licenses/dbcl/1-0/). `products-fi.js` on johdettu tietokanta ja jaetaan samalla ODbL-lisenssillä.

Puuttuuko tuote tai onko tieto väärin? Korjaus kannattaa tehdä suoraan Open Food Factsiin, jolloin se päivittyy tänne seuraavassa ajossa.
