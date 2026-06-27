#!/usr/bin/env python3
"""
bni_statement_to_csv.py — Convert a BNI account-statement PDF into the
semicolon-delimited bookkeeping CSV format.

Output columns:
    Posting_Date;Transaction_Date;Journal;Keterangan;Amount;DB_CR;Saldo;Jenis;_CEK

Notes
-----
* Words are read in the PDF's default positional order (NOT reading order), so
  the Keterangan column comes out in the same interleaved style as the existing
  bookkeeping files (e.g. "2,200,6108.00 BANKING DARI 731487718 ...").
* The garbled amount token "2,200,6108..0000" is cleaned to "2,200,6108.00" and
  kept inside Keterangan, exactly as in the reference file.
* The real Amount value is derived from the difference between consecutive
  Balance values (the PDF's own amount column is unreliable).

Usage:
    python3 bni_statement_to_csv.py input.pdf [output.csv]
"""

import csv
import re
import sys

import pdfplumber

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")
BALANCE_RE = re.compile(r"^[\d,]+\.\d{2}$")     # 8,271,251.00
DIGITS_RE = re.compile(r"^\d+$")


def clean_amount(tok):
    """'2,200,6108..0000' -> '2,200,6108.00' (kept verbatim in Keterangan)."""
    if ".." in tok:
        return tok.split("..")[0] + ".00"
    return tok


def collect_words(pdf):
    """All words across all pages in default positional order, page by page."""
    words = []
    for page in pdf.pages:
        words.extend(w["text"] for w in page.extract_words())
    return words


def find_opening_balance(words):
    for i, w in enumerate(words):
        if w == "Balance:" and i + 1 < len(words) and BALANCE_RE.match(words[i + 1]):
            return float(words[i + 1].replace(",", ""))
    return None


def is_txn_start(words, i):
    """A transaction starts with two timestamp pairs: date time date time."""
    return (
        i + 3 < len(words)
        and DATE_RE.match(words[i])
        and TIME_RE.match(words[i + 1])
        and DATE_RE.match(words[i + 2])
        and TIME_RE.match(words[i + 3])
    )


def parse(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        words = collect_words(pdf)

    opening = find_opening_balance(words)

    # Index every transaction start.
    starts = [i for i in range(len(words)) if is_txn_start(words, i)]

    rows = []
    prev_balance = opening
    for s, start in enumerate(starts):
        end = starts[s + 1] if s + 1 < len(starts) else len(words)
        toks = words[start:end]

        posting = toks[0]
        effective = toks[2]

        # Journal = first pure-digit token after the two timestamp pairs.
        # Any branch word(s) that sort before it are part of the prefix, not
        # the Keterangan.
        j_idx = None
        for k in range(4, min(len(toks), 12)):
            if DIGITS_RE.match(toks[k]):
                j_idx = k
                break
        if j_idx is None:
            continue
        journal = toks[j_idx]
        rest = toks[j_idx + 1:]

        # Locate the contiguous [amount][K|D][balance] triple.
        anchor = None
        for j in range(1, len(rest) - 1):
            if rest[j] in ("K", "D") and BALANCE_RE.match(rest[j + 1]):
                anchor = j
                break
        if anchor is None:
            continue

        db_cr = rest[anchor]
        balance = float(rest[anchor + 1].replace(",", ""))

        # Build Keterangan: drop the DB/CR token and EVERY balance-shaped token
        # (n,nnn.nn). The balance and the debit-style amount garble are both
        # balance-shaped and get removed; the credit-style amount garble
        # ("2,200,6108..0000") is not, so it stays and is cleaned in place.
        ket = []
        for k, tok in enumerate(rest):
            if k == anchor or BALANCE_RE.match(tok) or ",," in tok:
                continue
            ket.append(clean_amount(tok))
        keterangan = " ".join(ket)

        # Real amount from balance movement.
        if prev_balance is None:
            prev_balance = balance
        amount = abs(balance - prev_balance)
        prev_balance = balance

        jenis = "Penjualan" if db_cr == "K" else "Pembelian"
        amount_str = " Rp" + f"{amount:,.0f}".replace(",", ".") + " "

        rows.append([
            posting, effective, journal, keterangan,
            amount_str, db_cr, f"{balance}", jenis, "",
        ])
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 bni_statement_to_csv.py input.pdf [output.csv]")

    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else \
        pdf_path.rsplit(".", 1)[0] + "_converted.csv"

    rows = parse(pdf_path)
    if not rows:
        sys.exit("No transaction rows found.")

    header = ["Posting_Date", "Transaction_Date", "Journal", "Keterangan",
              "Amount", "DB_CR", "Saldo", "Jenis", "_CEK"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Wrote {len(rows)} transactions -> {out_path}")


if __name__ == "__main__":
    main()
