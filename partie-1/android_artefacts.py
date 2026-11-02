#!/usr/bin/env python3
"""Classe les enregistrements carves (sqlite_record_carver.py) dans les tables
Android 2.2 connues, en se basant sur le nombre de colonnes (schemas retrouves
dans sqlite_master) et sur des controles de type/plage de valeurs.
Convertit les dates (ms Unix) en UTC. Chaque ligne garde son offset dans
l'image pour la tracabilite.

Usage : android_artefacts.py dossier_csv_carves dossier_sortie
"""

import csv, datetime, os, re, sys

PHONE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")


def i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def is_ms(v):
    n = i(v)
    return n is not None and 1262304000000 <= n <= 1356998400000  # 2010-2012


def ms(v):
    n = i(v)
    if n is None:
        return ""
    if n > 10**11:
        n /= 1000
    return datetime.datetime.fromtimestamp(n, datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


SMS_TYPE = {
    "1": "recu",
    "2": "envoye",
    "3": "brouillon",
    "4": "boite d'envoi",
    "5": "echec",
    "6": "en file",
}
CALL_TYPE = {"1": "entrant", "2": "sortant", "3": "manque"}

# table : (nb colonnes, noms, validateur, colonnes date, decodeurs)
SPECS = {
    "sms": (
        14,
        "_id,thread_id,address,person,date,protocol,read,status,type,reply_path_present,subject,body,service_center,locked",
        lambda c: is_ms(c[4]) and c[8] in SMS_TYPE and i(c[1]) is not None,
        [4],
        {8: SMS_TYPE},
    ),
    "threads": (
        10,
        "_id,date,message_count,recipient_ids,snippet,snippet_cs,read,type,error,has_attachment",
        lambda c: (
            is_ms(c[1]) and i(c[2]) is not None and re.fullmatch(r"[0-9 ]+", c[3] or "")
        ),
        [1],
        {},
    ),
    "canonical_addresses": (
        2,
        "_id,address",
        lambda c: c[0] == "" and (PHONE.match(c[1]) or "@" in c[1]),
        [],
        {},
    ),
    "calls": (
        9,
        "_id,number,date,duration,type,new,name,numbertype,numberlabel",
        lambda c: is_ms(c[2]) and c[4] in CALL_TYPE,
        [2],
        {4: CALL_TYPE},
    ),
    "raw_contacts": (
        22,
        "_id,is_restricted,account_name,account_type,sourceid,version,dirty,deleted,contact_id,aggregation_mode,aggregation_needed,custom_ringtone,send_to_voicemail,times_contacted,last_time_contacted,starred,display_name,display_name_source,sync1,sync2,sync3,sync4",
        lambda c: i(c[5]) is not None and i(c[7]) in (0, 1),
        [14],
        {},
    ),
    "contacts_data": (
        26,
        "_id,package_id,mimetype_id,raw_contact_id,is_primary,is_super_primary,data_version,data1,data2,data3,data4,data5,data6,data7,data8,data9,data10,data11,data12,data13,data14,data15,data_sync1,data_sync2,data_sync3,data_sync4",
        lambda c: i(c[2]) is not None and i(c[3]) is not None,
        [],
        {},
    ),
    "mimetypes": (2, "_id,mimetype", lambda c: c[1].startswith("vnd.android"), [], {}),
    "browser_history_bookmarks": (
        11,
        "_id,title,url,visits,date,created,description,bookmark,favicon,thumbnail,touch_icon",
        lambda c: (
            (c[2] or "").startswith("http") and (is_ms(c[4]) or c[4] in ("", "0"))
        ),
        [4, 5],
        {},
    ),
    "gmail_messages": (
        21,
        "_id,messageId,conversation,fromAddress,toAddresses,ccAddresses,bccAddresses,replyToAddresses,dateSentMs,dateReceivedMs,subject,snippet,listInfo,personalLevel,body,bodyEmbedsExternalResources,joinedAttachmentInfos,synced,error,clientCreated,refMessageId",
        lambda c: "@" in (c[3] or "") + (c[4] or ""),
        [8, 9],
        {},
    ),
    "gmail_conversations": (
        14,
        "_id,queryId,subject,snippet,fromAddress,personalLevel,labelIds,numMessages,maxMessageId,hasAttachments,hasMessagesWithErrors,syncRationale,syncRationaleMessageId,forceAllUnread",
        lambda c: not is_ms(c[4]) and i(c[7]) is not None and i(c[8]) is not None,
        [],
        {},
    ),
    "talk_messages": (
        12,
        "_id,thread_id,nickname,body,date,real_date,type,packet_id,err_code,err_msg,is_muc,show_ts",
        lambda c: is_ms(c[4]) and i(c[1]) is not None,
        [4, 5],
        {},
    ),
    "accounts": (
        4,
        "_id,name,type,password",
        lambda c: "@" in c[1] and "." in c[2],
        [],
        {},
    ),
}


def main(src, out):
    os.makedirs(out, exist_ok=True)
    summary = []
    for table, (nc, names, ok, dates, dec) in SPECS.items():
        path = os.path.join(src, "rows_%02dcols.csv" % nc)
        if not os.path.exists(path):
            continue
        names = names.split(",")
        seen, rows = set(), []
        with open(path, newline="") as f:
            rd = csv.reader(f)
            next(rd)
            for r in rd:
                off, rowid, trunc, c = r[0], r[1], r[2], r[3:]
                if len(c) != nc:
                    continue
                try:
                    if not ok(c):
                        continue
                except (IndexError, TypeError):
                    continue
                key = (rowid, tuple(c))
                if key in seen:
                    continue
                seen.add(key)
                c[0] = c[0] or rowid  # INTEGER PRIMARY KEY = rowid
                extra = [ms(c[k]) for k in dates] + [
                    dec[k].get(c[k], c[k]) for k in dec
                ]
                rows.append([off, trunc] + extra + c)
        hdr = (
            ["offset_image", "tronque"]
            + [names[k] + "_utc" for k in dates]
            + [names[k] + "_libelle" for k in dec]
            + names
        )
        if dates:
            rows.sort(key=lambda r: r[2])
        with open(os.path.join(out, table + ".csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(rows)
        summary.append("%-26s %5d lignes  (rows_%02dcols.csv)" % (table, len(rows), nc))
    print("\n".join(summary))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
