#!/usr/bin/env python3
"""
bri_statement_to_csv.py — Convert a BRI "Laporan Transaksi Finansial"
(Statement of Financial Transaction) PDF into the BRI data-export CSV layout.

Columns (18): ID,NOREK,TGL_TRAN,TGL_EFEKTIF,JAM_TRAN,SEQ,DESK_TRAN,
SALDO_AWAL_MUTASI,MUTASI_DEBET,MUTASI_KREDIT,SALDO_AKHIR_MUTASI,GLSIGN,
TRUSER,KODE_TRAN,KODE_TRAN_TELLER,TRREMK,TLBDS1,TLBDS2

NOTE: SEQ, KODE_TRAN and KODE_TRAN_TELLER are internal BRI system codes that do
NOT appear in the PDF, so they are left blank. Every financial field
(dates, amounts, balances, Cr/Db, teller) is taken directly from the statement.

Usage:
    python3 bri_statement_to_csv.py input.pdf [output.csv]
"""

import csv
import re
import sys

import pdfplumber

AMT = re.compile(r"^[\d,]+\.\d{2}$")
MAIN = re.compile(r"^(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$")


def fmt(v):
    s = f"{v:.2f}"
    return s[1:] if s.startswith("0.") else s   # 0.00 -> .00


def collect(pdf):
    norek = ""
    lines = []
    for page in pdf.pages:
        pls = (page.extract_text() or "").splitlines()
        for l in pls:
            if not norek and l.startswith("No. Rekening"):
                m = re.search(r":\s*(\d+)", l)
                norek = m.group(1) if m else ""
        h = next((i for i, l in enumerate(pls) if l.startswith("Transaction Date")), None)
        for l in pls[(h + 1 if h is not None else 0):]:
            if l.startswith(("Halaman", "Page ", "Bersambung")):
                continue
            lines.append(l)
    return lines, norek


def parse(lines, norek):
    txns = []
    cur = None
    for l in lines:
        m = MAIN.match(l)
        toks = l.split()
        if m and len([t for t in toks if AMT.match(t)]) >= 3:
            if cur:
                txns.append(cur)
            d, tm, rest = m.group(1), m.group(2), m.group(3)
            rt = rest.split()
            amts = [t for t in rt if AMT.match(t)]
            deb, kre, sal = (float(a.replace(",", "")) for a in amts[-3:])
            idx = len(rt) - 3
            teller = rt[idx - 1] if idx - 1 >= 0 else ""
            desc = " ".join(rt[:idx - 1])
            dd, mm, yy = d.split("/")
            cur = {"date": f"20{yy}-{mm}-{dd} {tm}",
                   "jam": str(int(tm.replace(":", ""))),
                   "desc": desc, "esb": "",
                   "deb": deb, "kre": kre, "sal": sal, "teller": teller}
        elif cur is not None:
            cur["esb"] = (cur["esb"] + " " + l).strip()
    if cur:
        txns.append(cur)

    rows = []
    for i, t in enumerate(txns, 1):
        awal = t["sal"] - t["kre"] + t["deb"]
        desk = (t["desc"] + " " + t["esb"]).strip()
        # Cash (tunai) / e-wallet (dana) rows have no counterparty -> nodata
        trremk = "nodata" if re.search(r"tunai|dana", desk, re.I) else t["desc"]
        rows.append([
            str(i), norek, t["date"], t["date"], t["jam"], "",
            desk, fmt(awal), fmt(t["deb"]), fmt(t["kre"]), fmt(t["sal"]),
            "Cr" if t["kre"] > 0 else "Db", t["teller"], "", "",
            trremk, t["esb"], "",
        ])
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 bri_statement_to_csv.py input.pdf [output.csv]")
    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else \
        pdf_path.rsplit(".", 1)[0] + "_converted.csv"

    with pdfplumber.open(pdf_path) as pdf:
        lines, norek = collect(pdf)
    rows = parse(lines, norek)
    if not rows:
        sys.exit("No transactions found.")

    header = ["ID", "NOREK", "TGL_TRAN", "TGL_EFEKTIF", "JAM_TRAN", "SEQ",
              "DESK_TRAN", "SALDO_AWAL_MUTASI", "MUTASI_DEBET", "MUTASI_KREDIT",
              "SALDO_AKHIR_MUTASI", "GLSIGN", "TRUSER", "KODE_TRAN",
              "KODE_TRAN_TELLER", "TRREMK", "TLBDS1", "TLBDS2"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)
    print(f"Wrote {len(rows)} transactions -> {out_path}")


if __name__ == "__main__":
    main()
