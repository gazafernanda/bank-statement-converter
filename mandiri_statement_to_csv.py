#!/usr/bin/env python3
"""
mandiri_statement_to_csv.py — Convert a Mandiri Rekening Koran (Account
Statement) PDF into a semicolon-delimited CSV.

Columns: AccountNo;Ccy;PostDate;Remarks;AdditionalDesc;Credit Amount;Debit Amount;Close Balance

Close Balance is the statement's own printed running balance (validated against
Opening Balance ± each Credit/Debit).

Usage:
    python3 mandiri_statement_to_csv.py input.pdf [output.csv]
"""

import csv
import re
import sys

import pdfplumber

AMT = re.compile(r"[\d,]+\.\d{2}")
DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
TIME = re.compile(r"\d{2}:\d{2}:\d{2}")
TIMEF = re.compile(r"\d{2}:\d{2}:?\d{0,2}")
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def collect(pdf):
    acct = ccy = ""
    opening = None
    lines = []
    for page in pdf.pages:
        pls = (page.extract_text() or "").splitlines()
        for l in pls:
            if not acct and l.startswith("Account No"):
                m = re.search(r":\s*(\d+)", l)
                acct = m.group(1) if m else ""
            if not ccy and l.startswith("Currency"):
                ccy = l.split(":")[1].strip()
            if opening is None and l.startswith("Opening Balance"):
                m = AMT.search(l)
                if m:
                    opening = float(m.group().replace(",", ""))
        h = next((i for i, l in enumerate(pls) if l.startswith("Date & Time")), None)
        for l in pls[(h + 1 if h is not None else 0):]:
            if re.match(r"^Page \d+ of \d+$", l):
                continue
            lines.append(l)
    return lines, acct, ccy, opening


def is_main(l):
    return (DATE.match(l) and len(DATE.findall(l)) >= 2 and len(AMT.findall(l)) >= 3)


def parse(lines, acct, ccy):
    blocks = []
    cur = None
    for l in lines:
        if l.startswith("No of Credit"):
            break
        if is_main(l):
            if cur:
                blocks.append(cur)
            cur = [l]
        elif cur is not None:
            cur.append(l)
    if cur:
        blocks.append(cur)

    rows = []
    for b in blocks:
        main = b[0]
        amts = AMT.findall(main)
        deb, cre, bal = (float(a.replace(",", "")) for a in amts[-3:])
        dates = DATE.findall(main)
        i1 = main.index(dates[0])
        i2 = main.index(dates[1], i1 + len(dates[0]))
        after = main[i2 + len(dates[1]):]
        ref = after
        for a in amts[-3:]:
            ref = ref.replace(a, "")
        ref = TIMEF.sub("", ref)
        ref = re.sub(r"\s+", " ", ref).strip()
        tm = TIME.search(" ".join(b))
        time = tm.group() if tm else (TIMEF.search(main).group() if TIMEF.search(main) else "")
        desc = TIME.sub("", " ".join(b[1:]))
        desc = re.sub(r"\s+", " ", desc).strip()
        dd, mm, yy = dates[0].split("/")
        post = f"{dd} {MONTHS[int(mm) - 1]} {yy}" + (f" {time}" if time else "")
        remarks = (desc + ("  " + ref if ref else "")).strip()
        rows.append([acct, ccy, post, remarks, remarks,
                     f"{cre:.2f}", f"{deb:.2f}", f"{bal:.2f}"])
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 mandiri_statement_to_csv.py input.pdf [output.csv]")
    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else \
        pdf_path.rsplit(".", 1)[0] + "_converted.csv"

    with pdfplumber.open(pdf_path) as pdf:
        lines, acct, ccy, opening = collect(pdf)
    rows = parse(lines, acct, ccy)
    if not rows:
        sys.exit("No transactions found.")

    header = ["AccountNo", "Ccy", "PostDate", "Remarks", "AdditionalDesc",
              "Credit Amount", "Debit Amount", "Close Balance"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)
    print(f"Wrote {len(rows)} transactions -> {out_path}")
    print(f"Opening Balance: {opening:,.2f}")
    print(f"Closing Balance: {float(rows[-1][7]):,.2f}")


if __name__ == "__main__":
    main()
