#!/usr/bin/env bash
# Extraction complète de /data en root (tar), avec empreinte SHA-256 calculée SUR le téléphone
# pendant la copie. Le flux tar est dupliqué par tee : une copie vers le PC (adb exec-out),
# une copie vers sha256sum via un tube nommé dans /dev (tmpfs), donc rien n'est écrit dans /data.
# Usage : bash outils/extraction_complete.sh [dossier_sortie]
set -u

SORTIE="${1:-acquisition/complete}"
mkdir -p "$SORTIE"
TRACE="$SORTIE/trace_$(date -u +%Y%m%d_%H%M%SZ).txt"
ARCHIVE="$SORTIE/data.tar"

echo "Extraction complète de $(adb shell getprop ro.serialno | tr -d '\r') – début $(date -u -Iseconds)" > "$TRACE"
adb shell 'su -c "rm -f /dev/acq.fifo /dev/acq.sha256 /dev/acq.err; mkfifo /dev/acq.fifo"'

# stderr de tar part dans /dev/acq.err : exec-out mélangerait sinon les messages au flux binaire
adb exec-out 'su -c "sha256sum < /dev/acq.fifo > /dev/acq.sha256 & tar -cf - -C / data 2>/dev/acq.err | tee /dev/acq.fifo; wait"' > "$ARCHIVE"
echo "adb exec-out tar : rc=$? – fin $(date -u -Iseconds)" >> "$TRACE"

sleep 2
HASH_TEL="$(adb shell 'su -c "cat /dev/acq.sha256"' | awk '{print $1}')"
adb shell 'su -c "cat /dev/acq.err"' > "$SORTIE/tar_erreurs.txt"
adb shell 'su -c "rm -f /dev/acq.fifo /dev/acq.sha256 /dev/acq.err"'
HASH_PC="$(sha256sum "$ARCHIVE" | awk '{print $1}')"

{
    echo "Taille de l'archive : $(stat -c %s "$ARCHIVE") octets"
    echo "SHA-256 calculé sur le téléphone : $HASH_TEL"
    echo "SHA-256 calculé sur le PC        : $HASH_PC"
    [ -n "$HASH_TEL" ] && [ "$HASH_TEL" = "$HASH_PC" ] && echo "=> IDENTIQUES" || echo "=> DIFFÉRENTS"
    echo "Avertissements de tar : $(wc -l < "$SORTIE/tar_erreurs.txt") lignes (voir tar_erreurs.txt)"
} | tee -a "$TRACE"
echo "$HASH_PC  data.tar" > "$SORTIE/data.tar.sha256"
