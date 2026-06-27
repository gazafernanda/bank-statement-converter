#!/usr/bin/env python3
"""
bca_statement_to_csv.py — Convert a BCA e-statement (Mutasi Rekening) PDF into a
semicolon-delimited bookkeeping CSV.

Columns: Tanggal;Keterangan;Mutasi;DB_CR;Saldo;Jenis;_CEK

Saldo is computed from SALDO AWAL ± each Mutasi (CR adds, DB subtracts) and is
validated against the statement's printed SALDO AKHIR.

Usage:
    python3 bca_statement_to_csv.py input.pdf [output.csv]
"""

import csv
import re
import sys

import pdfplumber

AMT = re.compile(r"^[\d,]+\.\d{2}$")
DATE = re.compile(r"^\d{2}/\d{2}$")
NUMDUP = re.compile(r"^\d+\.\d{2}$")
SUMMARY = re.compile(r"^(SALDO AWAL|MUTASI CR|MUTASI DB|SALDO AKHIR)\s*:")


def idr(n):
    s = f"{n:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def extract_lines(pdf):
    year = ""
    lines = []
    for page in pdf.pages:
        pls = (page.extract_text() or "").splitlines()
        if not year:
            for l in pls:
                m = re.search(r"PERIODE\s*:\s*\S+\s+(\d{4})", l)
                if m:
                    year = m.group(1)
                    break
        h = next((i for i, l in enumerate(pls) if l.startswith("TANGGAL KETERANGAN")), None)
        start = h + 1 if h is not None else 0
        for l in pls[start:]:
            if l.startswith("Bersambung ke Halaman"):
                continue
            lines.append(l)
    return lines, year


def parse(lines, year):
    opening = bal = None
    txns = []
    cur = None

    def flush():
        nonlocal cur
        if cur:
            txns.append(cur)
            cur = None

    for l in lines:
        if SUMMARY.match(l):
            flush()
            break
        toks = l.split()
        if toks and DATE.match(toks[0]):
            if "SALDO AWAL" in l:
                m = [t for t in toks if AMT.match(t)]
                if m:
                    opening = float(m[-1].replace(",", ""))
                    bal = opening
                flush()
                continue
            if "SALDO AKHIR" in l:
                flush()
                continue
            flush()
            typ = "DB" if re.search(r"(^|\s)DB(\s|$)", l) else "CR"
            amts = [t for t in toks if AMT.match(t)]
            mut = float(amts[0].replace(",", "")) if amts else 0.0
            if bal is not None:
                bal = bal + mut if typ == "CR" else bal - mut
            main = [t for t in toks[1:] if not AMT.match(t)]
            if main and main[-1] == "DB":
                main.pop()
            cur = {"date": toks[0] + "/" + year, "typ": typ, "mut": mut,
                   "saldo": bal, "ket": list(main)}
        elif cur:
            for t in l.split():
                if t and not NUMDUP.match(t):
                    cur["ket"].append(t)
    flush()
    return txns, opening, bal


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 bca_statement_to_csv.py input.pdf [output.csv]")
    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else \
        pdf_path.rsplit(".", 1)[0] + "_converted.csv"

    with pdfplumber.open(pdf_path) as pdf:
        lines, year = extract_lines(pdf)
    txns, opening, closing = parse(lines, year)
    if not txns:
        sys.exit("No transactions found.")

    header = ["Tanggal", "Keterangan", "Mutasi", "DB_CR", "Saldo", "Jenis", "_CEK"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        for t in txns:
            ket = " ".join(t["ket"])
            ket = re.sub(r"\s+", " ", ket).strip()
            w.writerow([
                t["date"], ket, " Rp" + idr(t["mut"]) + " ", t["typ"],
                f"{t['saldo']:.2f}", "Penjualan" if t["typ"] == "CR" else "Pembelian", "",
            ])

    print(f"Wrote {len(txns)} transactions -> {out_path}")
    print(f"Saldo Awal : {opening:,.2f}")
    print(f"Saldo Akhir: {closing:,.2f} (computed)")


if __name__ == "__main__":
    main()
