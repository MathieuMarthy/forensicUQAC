#!/usr/bin/env bash
# Documentation technique du Pixel (étape 1 du sujet : préservation de la preuve).
# Lecture seule : uniquement des getprop / dumpsys / settings get, aucune écriture sur l'appareil.
# Usage : bash outils/documenter_appareil.sh [dossier_sortie]
set -u

SORTIE="${1:-documentation-appareil}"
HORODATAGE_EPOCH="$(date -u +%s)"
HORODATAGE="$(date -u -d "@${HORODATAGE_EPOCH}" +%Y%m%d_%H%M%SZ)"
DOSSIER="$SORTIE/$HORODATAGE"
mkdir -p "$DOSSIER/brut"
FICHE="$DOSSIER/fiche-appareil.md"

prop() { adb shell getprop "$1" | tr -d '\r'; }
brut() { # brut <nom> <commande shell> : sauvegarde la sortie complète
    adb shell "$2" > "$DOSSIER/brut/$1.txt" 2>&1
}

adb get-state >/dev/null 2>&1 || { echo "Aucun appareil adb autorisé." >&2; exit 1; }

# Horloges : l'écart PC / téléphone sert à recaler toutes les heures du rapport
PC_AVANT="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
TEL="$(adb shell date -u +%Y-%m-%dT%H:%M:%SZ | tr -d '\r')"
PC_APRES="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"

# Root : disponible seulement si Magisk a autorisé le shell
if adb shell 'su -c id' 2>/dev/null | grep -q 'uid=0'; then ROOT=oui; else ROOT=non; fi

# IMEI : nécessite le root sur Android 14 (sinon le relever avec *#06# et une photo)
IMEI="non lu (relever *#06# à l'écran)"
if [ "$ROOT" = oui ]; then
    I="$(adb shell "su -c 'service call iphonesubinfo 1 s16 com.android.shell'" | tr -d '\r' \
        | grep -o "'[^']*'" | tr -d "'. \n" )"
    [[ "$I" =~ ^[0-9]{15}$ ]] && IMEI="$I"
fi

brut batterie        'dumpsys battery'
brut stockage        'df -h /data /sdcard 2>/dev/null'
brut comptes         'dumpsys account'
brut telephonie      'dumpsys telephony.registry'
brut wifi_statut     'dumpsys wifi | head -60'
brut proprietes      'getprop'
brut paquets         'pm list packages -f -i -U'
brut paquets_tiers   'pm list packages -3'
brut uptime          'uptime'

BATT_NIV="$(grep -m1 ' level:' "$DOSSIER/brut/batterie.txt" | awk '{print $2}')"
BATT_SANTE="$(grep -m1 ' health:' "$DOSSIER/brut/batterie.txt" | awk '{print $2}')"
case "$BATT_SANTE" in 2) BATT_SANTE="bonne (2)";; 3) BATT_SANTE="surchauffe (3)";; 4) BATT_SANTE="morte (4)";; 7) BATT_SANTE="froide (7)";; esac
BATT_ALIM="$(grep -E '(AC|USB|Wireless) powered: true' "$DOSSIER/brut/batterie.txt" | sed 's/ powered: true//' | xargs)"
NB_TIERS="$(grep -c '^package:' "$DOSSIER/brut/paquets_tiers.txt")"
COMPTES="$(grep -oE 'Account \{name=[^,]*, type=[^}]*\}' "$DOSSIER/brut/comptes.txt" | sort -u | tr '\n' ';')"

cat > "$FICHE" <<EOF
# Fiche technique de l'appareil

Relevé automatique du $(date -u -d "@${HORODATAGE_EPOCH}" "+%Y-%m-%d %H:%M:%S") UTC par \`outils/documenter_appareil.sh\`.

## Identification
| Élément | Valeur |
|---|---|
| Fabricant / modèle | $(prop ro.product.manufacturer) $(prop ro.product.model) (\`$(prop ro.product.device)\`) |
| Numéro de série | $(prop ro.serialno) |
| IMEI | $IMEI |
| SKU matériel | $(prop ro.boot.hardware.sku) |
| Couleur / révision | $(prop ro.boot.hardware.color) / $(prop ro.boot.revision) |
| Mémoire | $(prop ro.boot.hardware.ddr) ; stockage $(prop ro.boot.hardware.ufs) |

## Logiciel
| Élément | Valeur |
|---|---|
| Version d'Android | $(prop ro.build.version.release) (API $(prop ro.build.version.sdk)) |
| Build | $(prop ro.build.id) |
| Empreinte | $(prop ro.build.fingerprint) |
| Correctif de sécurité | $(prop ro.build.version.security_patch) |
| Bootloader | $(prop ro.bootloader) |
| Baseband | $(prop gsm.version.baseband) |
| Noyau | $(adb shell uname -r | tr -d '\r') |

## Sécurité et état
| Élément | Valeur |
|---|---|
| Bootloader | verifiedbootstate=$(prop ro.boot.verifiedbootstate), flash.locked=$(prop ro.boot.flash.locked) |
| Slot actif | $(prop ro.boot.slot_suffix) |
| Chiffrement | $(prop ro.crypto.state) / $(prop ro.crypto.type) |
| Root (Magisk) | $ROOT |
| SIM | $(prop gsm.sim.state) ; opérateur : $(prop gsm.sim.operator.alpha) |
| Batterie | ${BATT_NIV}% ; santé : $BATT_SANTE ; alimentation : ${BATT_ALIM:-aucune} |
| Fuseau horaire | $(prop persist.sys.timezone) |
| Heure automatique | $(adb shell settings get global auto_time | tr -d '\r') |
| Mode avion | $(adb shell settings get global airplane_mode_on | tr -d '\r') |
| Applications tierces | $NB_TIERS |
| Comptes | ${COMPTES:-aucun} |

## Horloge
| Source | Heure UTC |
|---|---|
| PC avant lecture | $PC_AVANT |
| Téléphone | $TEL |
| PC après lecture | $PC_APRES |

## À compléter à la main
- État physique (rayures, écran, coque) :
- Photos de l'appareil (face, dos, étiquette SIM) :
- IMEI vérifié avec *#06# :
EOF

( cd "$DOSSIER" && find . -type f ! -name empreintes.sha256 -print0 | sort -z | xargs -0 sha256sum > empreintes.sha256 )
echo "$DOSSIER"
