# Treenikirja: tuotelista

Suomessa myytävien elintarvikkeiden ravintoarvot Treenikirja-sovelluksen viivakoodi- ja nimihakua varten.

## Miten tämä toimii

1. GitHub Actions ajaa maanantaisin skriptin `scripts/build_products.py`.
2. Skripti lataa Open Food Factsin koko CSV-viennin ja poimii tuotteet, jotka on merkitty Suomessa myytäviksi ja joilla on täydet ravintoarvot (energia, proteiini, hiilihydraatit, rasva per 100 g).
3. Tulos tallentuu tiedostoon `products-fi.js`, jos se muuttui.
4. Treenikirja lataa tiedoston jsDelivrin kautta:
   `https://cdn.jsdelivr.net/gh/vestomm/treenikirja-@main/products-fi.js`

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
  fields: ["code", "name", "brand", "kcal", "protein", "carbs", "fat", "nova", "nutriscore", "additives", "serving"],
  rows: [["6408430000135", "Maustamaton rahka", "Valio", 63, 11.5, 3.6, 0.2, 1, "a", 0, 250], ...]
};
```

Arvot ovat per 100 g. `nova`, `nutriscore`, `additives` ja `serving` voivat olla `null`.

## Lisenssi ja lähde

Tuotetiedot: [Open Food Facts](https://world.openfoodfacts.org), lisensoitu [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/) -lisenssillä. Yksittäisten tuotteiden sisältö: [Database Contents License](https://opendatacommons.org/licenses/dbcl/1-0/). `products-fi.js` on johdettu tietokanta ja jaetaan samalla ODbL-lisenssillä.

Puuttuuko tuote tai onko tieto väärin? Korjaus kannattaa tehdä suoraan Open Food Factsiin, jolloin se päivittyy tänne seuraavassa ajossa.
