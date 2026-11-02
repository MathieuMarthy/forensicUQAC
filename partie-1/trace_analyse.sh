#!/usr/bin/env bash
# Rejoue l'analyse DFRWS 2011 Case 1 et journalise chaque commande + sortie.
# Usage : bash outils/trace_analyse.sh   (depuis le dossier du projet)
cd "$(dirname "$0")/.." || exit 1
LOG="rapport/traces_$(date +%Y%m%d_%H%M%S).txt"
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

run() {
  { echo; echo "[$(date '+%Y-%m-%d %H:%M:%S')] \$ $*"; } >>"$LOG"
  eval "$@" >>"$LOG" 2>&1
  echo "[code retour: $?]" >>"$LOG"
}
section() { printf '\n==================== %s ====================\n' "$1" >>"$LOG"; }

section "1. Environnement"
run 'uname -a'
run 'fls -V'
run 'python3 --version'
run 'sha256sum outils/*.py'

section "2. Integrite des preuves"
run 'cat postAcquisitionHashes.txt SDCard.md5'
run 'md5sum mtdblock*.img SDCard.img'

section "3. Identification des images"
run 'file *.img'
run 'ls -l *.img'
run 'grep -A12 "cat /proc/partitions" cmd2.txt | head -14'
run 'grep -E "mtdblock[0-9] /" cmd2.txt'
run 'grep "dd if=" cmd2.txt | sort -u'

section "4. Carte SD : lisible par Sleuth Kit / Autopsy (FAT32)"
run 'mmls -t dos SDCard.img'
run 'fsstat -o 129 SDCard.img | head -25'
run 'fls -o 129 SDCard.img | head -30'

section "5. Partitions YAFFS2 : echec de Sleuth Kit (moteur d Autopsy)"
for i in 0 4 5 6; do
  run "fsstat mtdblock$i.img"
  run "fsstat -f yaffs2 mtdblock$i.img"
  run "fls -f yaffs2 mtdblock$i.img"
done

section "5b. Essai avec fichier de configuration YAFFS2 de TSK (sans zone spare)"
ln -s "$PWD/mtdblock6.img" "$TMPD/mtdblock6.img"
printf 'flash_page_size = 2048\nflash_spare_size = 0\nspare_seq_num_offset = 0\nspare_obj_id_offset = 4\nspare_chunk_id_offset = 8\n' >"$TMPD/mtdblock6.img-yaffs2.config"
run "cat '$TMPD/mtdblock6.img-yaffs2.config'"
run "fsstat -f yaffs2 '$TMPD/mtdblock6.img'"

section "6. Preuve de l absence de zone OOB (spare)"
run 'python3 -I - <<PY
import os
parts = {0:1536, 4:143744, 5:94848, 6:268032}   # /proc/partitions (Ko), cmd2.txt
for i, kb in parts.items():
    s = os.path.getsize("mtdblock%d.img" % i)
    pages = kb * 1024 // 2048
    print("mtdblock%d : taille image=%d  attendu sans OOB=%d  attendu avec OOB(64o/page)=%d  -> %s"
          % (i, s, kb * 1024, pages * 2112, "SANS OOB" if s == kb * 1024 else "?"))
PY'
run 'python3 -I - <<PY
d = open("mtdblock6.img", "rb").read()
print("page 462 (debut mmssms.db) :", d[462*2048:462*2048+16])
print("page 464 (en-tete objet YAFFS2) :", d[464*2048:464*2048+20].hex())
print("16 derniers octets page 464 :", d[465*2048-16:465*2048].hex(), "(pas de tags inband)")
PY'

section "7. Extraction par en-tetes YAFFS2 (outils/yaffs2_noob_extract.py)"
for p in 0:config 4:system 5:cache 6:data; do
  i=${p%%:*}; n=${p#*:}
  run "python3 -I outils/yaffs2_noob_extract.py mtdblock$i.img analyse/$n/fichiers"
done
run 'grep -E ",(mmssms|contacts2)\.db," analyse/data/fichiers/headers.csv | cut -d, -f1-11 | head'

section "8. Carving des enregistrements SQLite (outils/sqlite_record_carver.py)"
for p in 0:config 4:system 5:cache 6:data; do
  i=${p%%:*}; n=${p#*:}
  run "python3 -I outils/sqlite_record_carver.py mtdblock$i.img analyse/$n/sqlite"
done
run 'wc -l analyse/data/sqlite/*.csv'
run 'grep -h "gold" analyse/data/sqlite/*.csv | head -5'

section "10. Classement des enregistrements en tables Android (outils/android_artefacts.py)"
run 'python3 -I outils/android_artefacts.py analyse/data/sqlite analyse/data/artefacts'
run 'grep -ic "^create table" analyse/data/schemas_sqlite.txt'
run 'cut -d, -f3,6,7,10- analyse/data/artefacts/calls.csv'
run 'grep -E ",(envoye|brouillon|recu)," analyse/data/artefacts/sms.csv | grep -v ksms | cut -d, -f3,5,6,9-'

section "11. Carte SD : fichiers, export et metadonnees"
run 'fls -r -p -o 129 SDCard.img | tee analyse/sdcard_fls.txt | grep -E "download/|DCIM/|\\* "'
run 'mkdir -p analyse/sdcard_export; grep -E "^r/r [0-9]+:.(download|DCIM/Camera)/" analyse/sdcard_fls.txt | while IFS=$(printf "\\t") read -r a fp; do ino=${a#r/r }; ino=${ino%:}; icat -o 129 SDCard.img $ino > "analyse/sdcard_export/${fp##*/}"; done; ls -l analyse/sdcard_export'
run 'istat -o 129 SDCard.img 3080 | grep -E "Written|Accessed|Created"'
run 'sha256sum analyse/sdcard_export/*'
run 'for f in analyse/sdcard_export/*.pdf; do echo "== $f"; pdfinfo "$f" | grep -E "^(Title|Author|Creator|CreationDate)"; pdftotext -l 1 "$f" - | tr -s "\\n " " " | cut -c1-160; echo; done'
run 'file analyse/sdcard_export/*.jpg; strings -n 6 "analyse/sdcard_export/2011-05-06 14.43.35.jpg" | head -3'

section "12. Chronologie"
run 'python3 -I outils/chronologie.py analyse rapport/chronologie.csv && cat rapport/chronologie.csv'

section "13. Empreintes des resultats"
run 'find analyse rapport/chronologie.csv -name "*.csv" -exec sha256sum {} +'

echo "Trace ecrite dans $LOG"
