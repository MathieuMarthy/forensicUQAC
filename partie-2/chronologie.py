#!/usr/bin/env python3
"""Fusionne les artefacts (SMS, appels, Gmail, navigateur, contacts, carte SD)
en une chronologie unique triee (UTC), dedoublonnee.
Les SMS automatiques 'ksms' (thread 1) sont resumes : seuls les transferts
(FORWARDED SMS, CallIn/CallOut) sont gardes.
Usage : chronologie.py dossier_analyse sortie.csv
"""

import csv, datetime, os, re, subprocess, sys


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main(base, out):
    a = os.path.join(base, "data", "artefacts")
    ev = set()
    for r in rows(os.path.join(a, "sms.csv")):
        body = r["body"].replace("\n", " ")
        if body.startswith("ksms") and not re.search(r"FORWARDED|CallIn|CallOut", body):
            continue
        ev.add(
            (
                r["date_utc"],
                "SMS " + r["type_libelle"],
                r["address"],
                body[:200],
                r["offset_image"],
            )
        )
    for r in rows(os.path.join(a, "calls.csv")):
        ev.add(
            (
                r["date_utc"],
                "Appel " + r["type_libelle"],
                r["number"] + " " + r["name"],
                "duree %ss" % r["duration"],
                r["offset_image"],
            )
        )
    seen = set()
    for r in rows(os.path.join(a, "gmail_messages.csv")):
        if r["messageId"] in seen:
            continue
        seen.add(r["messageId"])
        ev.add(
            (
                r["dateSentMs_utc"],
                "Gmail",
                r["fromAddress"] + " -> " + r["toAddresses"],
                (r["subject"] + " : " + r["snippet"]).replace("\n", " ")[:200],
                r["offset_image"],
            )
        )
    for r in rows(os.path.join(a, "browser_history_bookmarks.csv")):
        if r["date_utc"] > "2000":
            ev.add(
                (
                    r["date_utc"],
                    "Navigateur",
                    r["title"][:80],
                    r["url"][:200],
                    r["offset_image"],
                )
            )
    # carte SD : dates de creation FAT (heure locale EDT, UTC-4)
    fls = os.path.join(base, "sdcard_fls.txt")
    img = os.path.join(base, "..", "SDCard.img")
    for line in open(fls):
        m = re.match(r"r/r (\d+):\t((download|DCIM/Camera)/.*)", line.rstrip("\n"))
        if not m:
            continue
        st = subprocess.run(
            ["istat", "-o", "129", img, m.group(1)], capture_output=True, text=True
        ).stdout
        c = re.search(r"Created:\t(\S+ \S+)", st)
        if c:
            t = datetime.datetime.strptime(
                c.group(1), "%Y-%m-%d %H:%M:%S"
            ) + datetime.timedelta(hours=4)
            ev.add(
                (
                    t.strftime("%Y-%m-%d %H:%M:%S"),
                    "Carte SD (creation)",
                    m.group(2),
                    "",
                    "inode " + m.group(1),
                )
            )
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["date_utc", "source", "interlocuteur_ou_titre", "contenu", "provenance"]
        )
        uniq = {}
        for e in sorted(ev):  # meme evenement vu a plusieurs offsets
            uniq.setdefault(e[:4], e)
        w.writerows(uniq.values())
    print("%d evenements -> %s" % (len(uniq), out))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
