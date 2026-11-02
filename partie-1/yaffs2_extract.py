#!/usr/bin/env python3
"""Reconstruit les fichiers d'une image YAFFS2 acquise SANS zone OOB
(dd if=/dev/block/mtdblockX). Sans OOB, les tags YAFFS2 (objectId, chunkId)
sont perdus : on suppose que les chunks de donnees d'un fichier precedent
immediatement son en-tete d'objet (ecriture sequentielle du log YAFFS2).
Chaque en-tete trouve donne une version du fichier (y compris anciennes
versions / fichiers supprimes encore presents dans la NAND).

Usage : yaffs2_noob_extract.py image.img dossier_sortie
"""

import csv, datetime, os, struct, sys

PAGE = 2048
TYPES = {1: "file", 2: "symlink", 3: "dir", 4: "hardlink"}


def parse_header(p):
    t, parent = struct.unpack_from("<II", p, 0)
    if t not in TYPES or p[8:10] != b"\xff\xff" or parent > 0x40000:
        return None
    name = p[10:266].split(b"\0")[0]
    if not name or not all(32 <= c < 127 for c in name):
        return None
    mode, uid, gid, atime, mtime, ctime, size = struct.unpack_from("<7I", p, 268)
    alias = p[300:460].split(b"\0")[0].decode("latin-1")
    return dict(
        type=TYPES[t],
        parent=parent,
        name=name.decode(),
        mode=mode,
        uid=uid,
        gid=gid,
        atime=atime,
        mtime=mtime,
        ctime=ctime,
        size=size if size != 0xFFFFFFFF else 0,
        alias=alias,
    )


def ts(x):
    try:
        return datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def main(img, out):
    data = open(img, "rb").read()
    npages = len(data) // PAGE
    headers = {}
    for i in range(npages):
        h = parse_header(data[i * PAGE : (i + 1) * PAGE])
        if h:
            headers[i] = h
    os.makedirs(os.path.join(out, "files"), exist_ok=True)
    rows = []
    for i, h in sorted(headers.items()):
        status = ""
        if h["type"] == "file" and h["size"]:
            n = -(-h["size"] // PAGE)
            start = i - n
            if start < 0 or any(j in headers for j in range(start, i)):
                status = "incomplet (chunks non contigus)"
            else:
                blob = data[start * PAGE : i * PAGE][: h["size"]]
                fn = "%s__p%07d" % (h["name"].replace("/", "_"), i)
                with open(os.path.join(out, "files", fn), "wb") as f:
                    f.write(blob)
                status = fn
        rows.append(
            [
                i,
                h["type"],
                h["name"],
                h["parent"],
                h["size"],
                oct(h["mode"]),
                h["uid"],
                h["gid"],
                ts(h["atime"]),
                ts(h["mtime"]),
                ts(h["ctime"]),
                h["alias"],
                status,
            ]
        )
    with open(os.path.join(out, "headers.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "page",
                "type",
                "name",
                "parent_id",
                "size",
                "mode",
                "uid",
                "gid",
                "atime_utc",
                "mtime_utc",
                "ctime_utc",
                "alias",
                "extracted_as",
            ]
        )
        w.writerows(rows)
    print(
        "%d en-tetes, %d fichiers extraits -> %s"
        % (
            len(rows),
            sum(1 for r in rows if r[-1] and not r[-1].startswith("incomplet")),
            out,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
