#!/usr/bin/env python3
"""Chronologie consolidée du Pixel (partie 2), sur le modèle de chronologie.py (partie 1).
Fusionne WhatsApp, SMS, Chrome, Gmail, Google Drive, photos (EXIF), corbeille Photos, Timeline,
presse-papiers Gboard et bugreport en une liste triée (UTC + heure locale), dédoublonnée, chaque ligne
gardant sa provenance. Toutes les bases sont lues en lecture seule.
Usage : chronologie_pixel.py dossier_projet sortie.csv
"""

import csv, datetime, glob, json, os, re, sqlite3, subprocess, sys
from fractions import Fraction

UTC = datetime.timezone.utc
LOCAL = datetime.timezone(datetime.timedelta(hours=-4), "EDT")
DEBUT, FIN = (
    "2026-10-28 13:00:00",
    "2026-10-28 17:00:00",
)  # jour J en UTC (09:00 → 13:00 EDT)


def ms(t):
    return datetime.datetime.fromtimestamp(t / 1000, UTC)


def chrome(t):  # microsecondes depuis 1601
    return datetime.datetime(1601, 1, 1, tzinfo=UTC) + datetime.timedelta(
        microseconds=t
    )


def ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


def main(base, out):
    ext = os.path.join(base, "analyse", "travail")  # copies de travail des bases
    tsv = glob.glob(
        os.path.join(base, "analyse", "aleapp", "ALEAPP_Output_*", "_TSV Exports")
    )[0]
    ev = set()

    db = ro(os.path.join(ext, "whatsapp", "msgstore.db"))
    types = {
        0: "texte",
        1: "image",
        7: "système",
        9: "document",
        15: "SUPPRIMÉ pour tous",
    }
    for i, ts, me, typ, txt in db.execute(
        "select _id, timestamp, from_me, message_type, text_data from message where timestamp > 0"
    ):
        ev.add(
            (
                ms(ts),
                "WhatsApp " + ("envoyé" if me else "reçu"),
                "E. (@lid)",
                "[%s] %s" % (types.get(typ, typ), txt or ""),
                "msgstore.db message._id=%d" % i,
            )
        )
    for i, t in db.execute(
        "select message_row_id, edited_timestamp from message_edit_info"
    ):
        ev.add(
            (
                ms(t),
                "WhatsApp modification",
                "E. (@lid)",
                "message %d modifié" % i,
                "msgstore.db message_edit_info",
            )
        )
    for i, t in db.execute(
        "select message_row_id, revoke_timestamp from message_revoked"
    ):
        ev.add(
            (
                ms(t),
                "WhatsApp révocation",
                "E. (@lid)",
                "message %d supprimé pour tous" % i,
                "msgstore.db message_revoked",
            )
        )

    db = ro(os.path.join(ext, "sms", "mmssms.db"))
    for i, d, typ, adr, corps in db.execute(
        "select _id, date, type, address, body from sms"
    ):
        ev.add(
            (
                ms(d),
                "SMS " + {1: "reçu", 2: "envoyé"}.get(typ, str(typ)),
                adr,
                (corps or "").replace("\n", " ")[:120],
                "mmssms.db sms._id=%d" % i,
            )
        )

    db = ro(os.path.join(ext, "chrome", "History"))
    for t, url, titre in db.execute(
        "select v.visit_time, u.url, u.title from visits v join urls u on u.id=v.url"
    ):
        ev.add(
            (
                chrome(t),
                "Chrome visite",
                (titre or "")[:60],
                url[:120],
                "History visits",
            )
        )
    for t, url, chemin in db.execute(
        "select start_time, tab_url, target_path from downloads"
    ):
        ev.add((chrome(t), "Chrome téléchargement", url, chemin, "History downloads"))

    csv.field_size_limit(10**8)
    with open(
        os.path.join(tsv, "Gmail - App Emails.tsv"), encoding="utf-8-sig", newline=""
    ) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            t = datetime.datetime.fromisoformat(r["Timestamp"])
            ev.add(
                (
                    t,
                    "Gmail",
                    (r["Mailed By"] or "") + " -> " + (r["Recipient"] or ""),
                    (r["Subject Line"] + " : " + r["Message"]).replace("\n", " ")[:120]
                    + (
                        " [PJ %s]" % r["Attachment Name"]
                        if r["Attachment Name"]
                        else ""
                    ),
                    "bigTopDataDB (ALEAPP)",
                )
            )
    with open(
        os.path.join(tsv, "Gboard - Clipboard.tsv"), encoding="utf-8-sig", newline=""
    ) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            texte = r["Text"]
            if re.fullmatch(r"[0-9a-fA-F ]{64,}", texte):
                texte = "<clé de 64 caractères masquée>"
            ev.add(
                (
                    datetime.datetime.fromisoformat(r["Timestamp"]),
                    "Gboard presse-papiers",
                    "",
                    texte[:80],
                    "Gboard clipboard (ALEAPP)",
                )
            )
    with open(
        os.path.join(tsv, "Cello - Google Drive.tsv"), encoding="utf-8-sig", newline=""
    ) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["Folder"] != "Yes":
                ev.add(
                    (
                        datetime.datetime.fromisoformat(r["Created Date"]),
                        "Google Drive envoi",
                        r["File Name"],
                        "%s, %s octets" % (r["Mime Type"], r["Quota Size"]),
                        "app_cello (ALEAPP)",
                    )
                )

    for photo in sorted(
        glob.glob(
            os.path.join(
                base, "acquisition", "logique", "sdcard", "DCIM", "Camera", "*.jpg"
            )
        )
        + glob.glob(
            os.path.join(
                base,
                "acquisition",
                "logique",
                "sdcard",
                "DCIM",
                "Camera",
                ".trashed-*.jpg",
            )
        )
    ):
        nom = os.path.basename(photo)
        exif = subprocess.run(
            [
                "magick",
                "identify",
                "-format",
                "%[EXIF:DateTimeOriginal]|%[EXIF:OffsetTimeOriginal]|%[EXIF:GPSLatitude]|%[EXIF:GPSLongitude]",
                photo,
            ],
            capture_output=True,
            text=True,
        ).stdout.split("|")
        t = datetime.datetime.strptime(
            exif[0] + exif[1].replace(":", ""), "%Y:%m:%d %H:%M:%S%z"
        )
        dms = [
            [float(Fraction(x)) for x in v.split(",")] for v in exif[2:4]
        ]  # "48/1,25/1,1179/100"
        lat, lon = (d + m / 60 + s / 3600 for d, m, s in dms)
        ev.add(
            (
                t,
                "Photo (EXIF)",
                nom,
                "GPS %.6f, -%.6f" % (lat, lon),
                "DCIM/Camera (extraction logique)",
            )
        )
        m = re.match(r"\.trashed-(\d+)-", nom)
        if m:  # expiration de la corbeille = suppression + 30 jours
            t = datetime.datetime.fromtimestamp(
                int(m.group(1)), UTC
            ) - datetime.timedelta(days=30)
            ev.add(
                (
                    t,
                    "Photo mise à la corbeille",
                    nom,
                    "expiration %s - 30 j" % m.group(1),
                    "nom de fichier .trashed-",
                )
            )

    tl = json.load(
        open(os.path.join(base, "acquisition", "complementaire", "Timeline.json"))
    )
    for s in tl["semanticSegments"]:
        t = datetime.datetime.fromisoformat(s["startTime"])
        fin = (
            datetime.datetime.fromisoformat(s["endTime"])
            .astimezone(LOCAL)
            .strftime("%H:%M:%S")
        )
        if "visit" in s:
            ll = s["visit"]["topCandidate"]["placeLocation"]["latLng"]
            ev.add(
                (
                    t,
                    "Timeline visite",
                    "jusqu'à " + fin,
                    ll,
                    "Timeline.json semanticSegments",
                )
            )
        elif "activity" in s:
            a = s["activity"]
            ev.add(
                (
                    t,
                    "Timeline trajet",
                    "jusqu'à " + fin,
                    "%s %.0f m -> %s"
                    % (
                        a["topCandidate"]["type"],
                        a["distanceMeters"],
                        a["end"]["latLng"],
                    ),
                    "Timeline.json semanticSegments",
                )
            )

    # bugreport : journaux système en heure locale, sans année
    rapport = glob.glob(os.path.join(base, "analyse", "bugreport", "bugreport-*.txt"))[
        0
    ]
    vus = set()
    for ligne in open(rapport, encoding="utf-8", errors="replace"):
        m = re.search(
            r"(10-2[78] \d\d:\d\d:\d\d)\.\d+ .*AirplaneModeStats: Airplane mode change\. Value: (\w+)",
            ligne,
        )
        if m:
            t = datetime.datetime.strptime(
                "2026-" + m.group(1), "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=LOCAL)
            ev.add(
                (
                    t,
                    "Mode avion",
                    "",
                    "activé" if m.group(2) == "true" else "désactivé",
                    "bugreport AirplaneModeStats",
                )
            )
        m = re.search(
            r"(10-2[78] \d\d:\d\d:\d\d)\.\d+,onCapabilitiesChanged: network=(\d+),.*?SSID: \"([^\"]*)\"",
            ligne,
        )
        if m and m.group(2) not in vus:  # première apparition d'un réseau = connexion
            vus.add(m.group(2))
            t = datetime.datetime.strptime(
                "2026-" + m.group(1), "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=LOCAL)
            ev.add(
                (
                    t,
                    "Wi-Fi connexion",
                    m.group(3),
                    "network=" + m.group(2),
                    "bugreport NetworkCallback",
                )
            )
        m = re.search(
            r"(2026-10-2[78])T(\d\d:\d\d:\d\d)\.\d+ - removeNetworkInternal: removed config\. .*configKey=\"([^\"]*)\"",
            ligne,
        )
        if m:
            t = datetime.datetime.strptime(
                m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=LOCAL)
            ev.add(
                (
                    t,
                    "Wi-Fi réseau supprimé",
                    m.group(3),
                    "configuration effacée",
                    "bugreport removeNetworkInternal",
                )
            )

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date_utc",
                "heure_locale",
                "source",
                "interlocuteur_ou_titre",
                "contenu",
                "provenance",
            ]
        )
        uniq = {}
        for t, *reste in sorted(ev, key=lambda e: (e[0].astimezone(UTC), e[1:])):
            u = t.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
            if DEBUT <= u <= FIN:
                uniq.setdefault(
                    (u, *reste[:3]),
                    [u, t.astimezone(LOCAL).strftime("%H:%M:%S"), *reste],
                )
        w.writerows(uniq.values())
    print("%d événements -> %s" % (len(uniq), out))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
