"""Génère les faux plans « SWIFTLOGIC – Projet 2228 » (SVG) à photographier le jour J.

Usage : python3 -I outils/generer_plans.py <dossier_sortie>
Puis : rsvg-convert -f pdf -o plans_2228.pdf <dossier>/*.svg
"""

import random
import sys
from pathlib import Path

L, H = 1123, 794  # A4 paysage à 96 dpi

FEUILLES = [
    (3, "Module de contrôle thermique – vue de dessus"),
    (7, "Carte de puissance – implantation"),
    (12, "Boîtier – coupe A-A"),
]


def dessin(rng):
    """Dessin technique simple : pièces, perçages, cotes."""
    e = []
    for _ in range(6):
        x, y = rng.randint(80, 640), rng.randint(110, 480)
        w, h = rng.randint(80, 220), rng.randint(50, 160)
        e.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#123" stroke-width="2"/>'
        )
        e.append(
            f'<line x1="{x}" y1="{y + h + 18}" x2="{x + w}" y2="{y + h + 18}" stroke="#123" '
            f'marker-start="url(#f)" marker-end="url(#f)"/>'
        )
        e.append(
            f'<text x="{x + w / 2}" y="{y + h + 14}" font-size="11" text-anchor="middle">{w * 0.5:.1f}</text>'
        )
    for _ in range(10):
        x, y, r = rng.randint(100, 800), rng.randint(120, 560), rng.randint(6, 22)
        e.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="#123" stroke-width="1.5"/>'
        )
        e.append(
            f'<path d="M{x - r - 6} {y}h{2 * r + 12}M{x} {y - r - 6}v{2 * r + 12}" '
            f'stroke="#123" stroke-dasharray="6 3" stroke-width=".7"/>'
        )
    return "\n".join(e)


def feuille(num, titre):
    rng = random.Random(2228 + num)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{H}" viewBox="0 0 {L} {H}"
 font-family="DejaVu Sans, sans-serif" fill="#123">
<defs><marker id="f" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M0 0L10 5L0 10z"/></marker></defs>
<rect width="{L}" height="{H}" fill="#fff"/>
<rect x="30" y="30" width="{L - 60}" height="{H - 60}" fill="none" stroke="#123" stroke-width="3"/>
<text x="50" y="75" font-size="26" font-weight="bold">SWIFTLOGIC, Inc – Projet 2228</text>
<text x="50" y="100" font-size="15">{titre}</text>
<text x="{L - 50}" y="75" font-size="26" font-weight="bold" fill="#b00" text-anchor="end">CONFIDENTIEL</text>
<text x="{L - 50}" y="100" font-size="13" fill="#b00" text-anchor="end">Diffusion interne uniquement – ne pas reproduire</text>
{dessin(rng)}
<g transform="translate({L - 380} {H - 170})">
<rect width="350" height="140" fill="#fff" stroke="#123" stroke-width="2"/>
<path d="M0 35h350M0 70h350M0 105h350M175 35v105" stroke="#123"/>
<text x="10" y="24" font-size="14" font-weight="bold">Swift Logic Technologies – Saguenay</text>
<text x="10" y="58" font-size="12">Projet : 2228</text>
<text x="185" y="58" font-size="12">Feuille {num} / 37</text>
<text x="10" y="93" font-size="12">Ingénieur : Y. Taog</text>
<text x="185" y="93" font-size="12">Rév. C – 2026-10-14</text>
<text x="10" y="128" font-size="12">Réf. : SL-2228-{num:03d}</text>
<text x="185" y="128" font-size="12">Classification : INTERNE</text>
</g>
<text x="{L / 2}" y="{H / 2}" font-size="110" font-weight="bold" fill="#b00" fill-opacity=".10"
 text-anchor="middle" transform="rotate(-25 {L / 2} {H / 2})">CONFIDENTIEL</text>
</svg>'''


def main():
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    for num, titre in FEUILLES:
        (sortie / f"2228-{num:02d}.svg").write_text(
            feuille(num, titre), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
