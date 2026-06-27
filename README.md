# Bank Statement → CSV

Convert Indonesian bank **e-statement PDFs** into clean CSV for bookkeeping.
Supports **BCA**, **BNI**, **Mandiri**, and **BRI**.

Live web app: https://gazafernanda.github.io/bank-statement-converter/

There are two ways to use it:

- **`index.html`** — a single-file web app. Open it in a browser, drop a PDF, and
  download the CSV. The bank is **auto-detected**. Everything runs locally in the
  browser (via [pdf.js](https://mozilla.github.io/pdf.js/)) — your file never
  leaves your device. Requires an internet connection the first time to load
  pdf.js from a CDN.
- **Python CLI scripts** — for batch use or scripting.

## Web app

Open `index.html` in any modern browser. Leave the toggle on **Auto-detect**
(or pick BCA / BNI / Mandiri manually), drop a statement PDF, click **Convert**,
then **Download CSV**.

## Python CLI

Requires Python 3 and `pdfplumber`:

```bash
pip install pdfplumber
```

```bash
python3 bca_statement_to_csv.py      "BCA e-statement.pdf"        [output.csv]
python3 bni_statement_to_csv.py      "BNI statement.pdf"          [output.csv]
python3 mandiri_statement_to_csv.py  "Mandiri Rekening Koran.pdf" [output.csv]
python3 bri_statement_to_csv.py      "BRI Laporan Transaksi.pdf"  [output.csv]
```

Each script writes `<input>_converted.csv` next to the input if no output path
is given.

## How balances are handled

Each parser is validated against the statement's own printed balances:

- **BCA** — Saldo is derived from `Saldo Awal ± Mutasi` (the PDF doesn't print a
  balance on every row); validated against the printed balances and `Saldo Akhir`.
- **BNI** — Amount is derived from the movement between consecutive balances
  (the PDF's amount column is unreliable).
- **Mandiri** — uses the statement's printed running balance directly; validated
  against `Opening Balance ± Credit/Debit` and the `Closing Balance`.
- **BRI** — uses the statement's printed running balance; all financial fields
  validated 100% against the example export. Note: `SEQ`, `KODE_TRAN` and
  `KODE_TRAN_TELLER` are internal BRI system codes that do **not** appear in the
  PDF, so those columns are left blank.

## Privacy

This tool processes financial data. **No statement PDFs or converted CSVs are
included in this repository** (`.gitignore` blocks `*.pdf` and `*.csv`). The web
app does all parsing locally in your browser.
