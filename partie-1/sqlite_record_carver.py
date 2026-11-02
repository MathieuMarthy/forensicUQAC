#!/usr/bin/env python3
"""Carve les enregistrements SQLite (pages feuilles de table, type 0x0d)
directement dans une image brute (ex. mtdblock YAFFS2 sans OOB).
Retrouve aussi les anciennes versions de pages encore presentes en NAND.
Les cellules avec debordement (overflow) sont tronquees et marquees.

Sortie : un CSV par nombre de colonnes (rows_XXcols.csv), dedoublonne.
Usage : sqlite_record_carver.py image.img dossier_sortie [taille_page=1024]
"""

import csv, os, sys


def varint(b, i):
    v = 0
    for k in range(9):
        if i >= len(b):
            raise ValueError
        c = b[i]
        i += 1
        if k == 8:
            return (v << 8) | c, i
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, i
    return v, i


def value(t, b, i):
    if t == 0:
        return None, i
    if 1 <= t <= 6:
        n = (1, 2, 3, 4, 6, 8)[t - 1]
        if i + n > len(b):
            raise ValueError
        return int.from_bytes(b[i : i + n], "big", signed=True), i + n
    if t == 7:
        return "<float>", i + 8
    if t in (8, 9):
        return t - 8, i
    if t >= 12:
        n = (t - 12) // 2
        if i + n > len(b):
            raise ValueError
        raw = b[i : i + n]
        if t % 2:
            # base en UTF-16LE (PRAGMA encoding) : un octet nul sur deux
            if n >= 2 and n % 2 == 0 and raw[1::2].count(0) == n // 2:
                return raw.decode("utf-16-le", "replace"), i + n
            return raw.decode("utf-8", "replace"), i + n
        return "<blob %d o>" % n, i + n
    raise ValueError


def cells(page, psize):
    if page[0] != 0x0D:
        return
    n = int.from_bytes(page[3:5], "big")
    if n == 0 or 8 + 2 * n > psize:
        return
    usable = psize
    maxlocal = usable - 35
    for k in range(n):
        off = int.from_bytes(page[8 + 2 * k : 10 + 2 * k], "big")
        if off < 8 + 2 * n or off >= psize:
            continue
        try:
            plen, i = varint(page, off)
            rowid, i = varint(page, i)
            trunc = plen > maxlocal
            rec = page[i : i + min(plen, maxlocal)]
            hlen, j = varint(rec, 0)
            if hlen > len(rec) or hlen < 2:
                continue
            types = []
            while j < hlen:
                t, j = varint(rec, j)
                if t in (10, 11):
                    raise ValueError
                types.append(t)
            vals, p = [], hlen
            for t in types:
                try:
                    v, p = value(t, rec, p)
                except ValueError:
                    if not trunc:
                        raise
                    v = "<tronque>"
                    p = len(rec)
                vals.append(v)
            yield rowid, vals, trunc
        except ValueError:
            continue


def main(img, out, psize=1024):
    os.makedirs(out, exist_ok=True)
    seen = set()
    writers, files = {}, []
    with open(img, "rb") as f:
        data = f.read()
    for off in range(0, len(data) - psize + 1, psize):
        page = data[off : off + psize]
        for rowid, vals, trunc in cells(page, psize):
            key = (len(vals), rowid, tuple(map(str, vals)))
            if key in seen:
                continue
            seen.add(key)
            nc = len(vals)
            if nc not in writers:
                fh = open(os.path.join(out, "rows_%02dcols.csv" % nc), "w", newline="")
                files.append(fh)
                writers[nc] = csv.writer(fh)
                writers[nc].writerow(
                    ["offset_image", "rowid", "tronque"]
                    + ["c%d" % i for i in range(nc)]
                )
            writers[nc].writerow([off, rowid, int(trunc)] + vals)
    for fh in files:
        fh.close()
    print("%d enregistrements uniques -> %s" % (len(seen), out))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) == 4 else 1024)
