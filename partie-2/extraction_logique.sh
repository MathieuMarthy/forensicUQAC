#!/usr/bin/env bash
# Extraction logique SANS root (référence) : ce qu'un outil d'acquisition « standard »
# obtient par adb. Aucune commande su. Chaque commande est journalisée avec son code retour.
# Usage : bash outils/extraction_logique.sh [dossier_sortie]
set -u

SORTIE="${1:-acquisition/logique}"
mkdir -p "$SORTIE/dumpsys" "$SORTIE/content"
TRACE="$SORTIE/trace_$(date -u +%Y%m%d_%H%M%SZ).txt"
STOCKAGE=/storage/emulated/0

trace() { # trace <fichier_sortie> <commande adb shell>
    local debut code
    debut="$(date -u +%H:%M:%SZ)"
    adb shell "$2" > "$1" 2>&1
    code=$?
    printf '%s  rc=%s  %s  ->  %s\n' "$debut" "$code" "$2" "$1" >> "$TRACE"
}

echo "Extraction logique de $(adb shell getprop ro.serialno | tr -d '\r') – début $(date -u -Iseconds)" > "$TRACE"

# 1. Empreintes du stockage partagé calculées SUR le téléphone, avant la copie
trace "$SORTIE/empreintes_telephone.sha256" "cd $STOCKAGE && find . -type f -exec sha256sum {} +"

# 2. Copie du stockage partagé (DCIM, Download, Android/media/com.whatsapp…)
debut="$(date -u +%H:%M:%SZ)"
adb pull -a "$STOCKAGE/." "$SORTIE/sdcard" > "$SORTIE/pull_sdcard.txt" 2>&1
printf '%s  rc=%s  adb pull -a %s  ->  %s/sdcard\n' "$debut" "$?" "$STOCKAGE" "$SORTIE" >> "$TRACE"

# 3. Fournisseurs de contenu accessibles au shell
for uri in sms mms call_log/calls com.android.contacts/raw_contacts com.android.contacts/data; do
    trace "$SORTIE/content/${uri//\//_}.txt" "content query --uri content://$uri"
done

# 4. État du système
for svc in account package usagestats wifi location activity\ recents notification batterystats; do
    trace "$SORTIE/dumpsys/${svc// /_}.txt" "dumpsys $svc"
done
trace "$SORTIE/getprop.txt" "getprop"
trace "$SORTIE/paquets.txt" "pm list packages -f -i -U --show-versioncode"
trace "$SORTIE/paquets_desinstalles.txt" "pm list packages -u"

echo "Fin $(date -u -Iseconds)" >> "$TRACE"

# 5. Revérification sur le PC des empreintes calculées sur le téléphone
( cd "$SORTIE/sdcard" && sha256sum -c --quiet ../empreintes_telephone.sha256 ) \
    > "$SORTIE/verification_empreintes.txt" 2>&1
echo "Vérification des empreintes : rc=$? (0 = toutes identiques)" | tee -a "$TRACE"

( cd "$SORTIE" && find . -type f ! -name empreintes_pc.sha256 -print0 | sort -z | xargs -0 sha256sum > empreintes_pc.sha256 )
echo "$TRACE"
