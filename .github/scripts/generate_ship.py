#!/usr/bin/env python3
"""
Genera assets/contribution-fighter.svg

Una nave recorre tu gráfica de contribuciones de GitHub y destruye, columna por
columna, los días en los que hiciste commits. Usa SMIL (animación dentro del SVG),
así que funciona dentro de un README sin JavaScript.

Variables de entorno:
  GH_TOKEN   token de GitHub (obligatorio, salvo con DEMO=1)
  GH_USER    usuario de GitHub (obligatorio, salvo con DEMO=1)
  OUTPUT     ruta de salida (por defecto assets/contribution-fighter.svg)
  DEMO=1     usa datos aleatorios, útil para probar sin token
"""
import json
import os
import random
import sys
import urllib.request

# --------------------------------------------------------------------------- #
# Configuración visual
# --------------------------------------------------------------------------- #
CELL, GAP = 11, 3
PITCH = CELL + GAP
ROWS = 7
PAD_X, PAD_TOP = 24, 26
SWEEP = 24.0  # segundos que tarda la nave en recorrer la gráfica

LEVEL_COLORS = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]
LEVEL_NAMES = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
def fetch_weeks(user, token):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks { contributionDays { weekday contributionLevel } }
          }
        }
      }
    }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": user}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-fighter",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        sys.exit(f"Error al consultar GitHub: {payload}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [
        [(d["weekday"], LEVEL_NAMES.get(d["contributionLevel"], 0)) for d in w["contributionDays"]]
        for w in weeks
    ]


def demo_weeks(n=53):
    rnd = random.Random(7)
    weeks = []
    for _ in range(n):
        weeks.append([(d, rnd.choices([0, 1, 2, 3, 4], [38, 24, 18, 12, 8])[0]) for d in range(7)])
    return weeks


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def f(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def keytimes(*ts):
    assert all(a < b for a, b in zip(ts, ts[1:])), f"keyTimes no crecientes: {ts}"
    return ";".join(f(t) for t in ts)


# --------------------------------------------------------------------------- #
# Construcción del SVG
# --------------------------------------------------------------------------- #
def build_svg(weeks):
    n = len(weeks)
    width = PAD_X * 2 + n * PITCH - GAP
    grid_bottom = PAD_TOP + ROWS * PITCH - GAP
    ship_y = grid_bottom + 50
    height = ship_y + 30
    total = SWEEP + 4.0

    def col_x(c):
        return PAD_X + c * PITCH + CELL / 2

    x_first, x_last = col_x(0), col_x(n - 1)

    def hit_time(c):
        return 1.0 + SWEEP * c / max(n - 1, 1)

    out = []
    add = out.append
    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Nave espacial destruyendo la gráfica de contribuciones">'
    )
    add(
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0D1117"/><stop offset="1" stop-color="#0B1F17"/>'
        "</linearGradient>"
        '<linearGradient id="beam" x1="0" y1="1" x2="0" y2="0">'
        '<stop offset="0" stop-color="#39D353"/><stop offset="1" stop-color="#B7FFC9"/>'
        "</linearGradient></defs>"
    )
    add(f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10" fill="url(#bg)" stroke="#30363D"/>')

    # Estrellas
    rnd = random.Random(21)
    for i in range(70):
        sx, sy = rnd.uniform(8, width - 8), rnd.uniform(8, height - 8)
        r = rnd.choice([0.5, 0.6, 0.8, 1.0])
        op = rnd.uniform(0.25, 0.7)
        if i % 5 == 0:
            add(
                f'<circle cx="{f(sx)}" cy="{f(sy)}" r="{r}" fill="#C9D1D9" opacity="{f(op)}">'
                f'<animate attributeName="opacity" values="{f(op)};{f(min(op + .3, 1))};{f(op)}" '
                f'dur="{f(rnd.uniform(2.5, 5))}s" begin="{f(rnd.uniform(0, 3))}s" repeatCount="indefinite"/></circle>'
            )
        else:
            add(f'<circle cx="{f(sx)}" cy="{f(sy)}" r="{r}" fill="#C9D1D9" opacity="{f(op)}"/>')

    # Celdas (los días con actividad se destruyen)
    targets_by_col = {}
    for c, week in enumerate(weeks):
        for weekday, level in week:
            x = PAD_X + c * PITCH
            y = PAD_TOP + weekday * PITCH
            if level == 0:
                add(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS[0]}"/>')
                continue
            th = hit_time(c) + (ROWS - 1 - weekday) * 0.03
            targets_by_col.setdefault(c, []).append(th)
            kt = keytimes(0, th / total, (th + 0.12) / total, (total - 1.0) / total, 1)
            add(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS[level]}">'
                f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="{kt}" dur="{f(total)}s" repeatCount="indefinite"/>'
                f"</rect>"
            )
            # Explosión
            ke = keytimes(0, (th - 0.01) / total, th / total, (th + 0.4) / total, 1)
            cx, cy = x + CELL / 2, y + CELL / 2
            add(
                f'<circle cx="{f(cx)}" cy="{f(cy)}" r="0" fill="none" stroke="#7CFFA0" stroke-width="1.2" opacity="0">'
                f'<animate attributeName="r" values="0;0;1;8;8" keyTimes="{ke}" dur="{f(total)}s" repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" values="0;0;.9;0;0" keyTimes="{ke}" dur="{f(total)}s" repeatCount="indefinite"/>'
                f"</circle>"
            )

    # Láseres
    beam_top = PAD_TOP - 4
    beam_h = (ship_y - 20) - beam_top
    for c in sorted(targets_by_col):
        t = hit_time(c)
        kb = keytimes(0, (t - 0.05) / total, t / total, (t + 0.12) / total, (t + 0.25) / total, 1)
        add(
            f'<rect x="{f(col_x(c) - 1)}" y="{beam_top}" width="2" height="{beam_h}" rx="1" fill="url(#beam)" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kb}" dur="{f(total)}s" repeatCount="indefinite"/>'
            f"</rect>"
        )

    # Nave (diseño original, vista cenital)
    ks = keytimes(0, 1.0 / total, (1.0 + SWEEP) / total, (2.0 + SWEEP) / total, 1)
    values = ";".join(
        f"{f(x)},{ship_y}" for x in (x_first - 60, x_first, x_last, x_last + 70, x_last + 70)
    )
    add(f'<g transform="translate({f(x_first - 60)} {ship_y})">')
    add(
        f'<animateTransform attributeName="transform" type="translate" values="{values}" '
        f'keyTimes="{ks}" dur="{f(total)}s" repeatCount="indefinite"/>'
    )
    add(
        '<path d="M-3,10 L0,19 L3,10Z" fill="#39D353">'
        '<animate attributeName="opacity" values="1;.45;1" dur=".25s" repeatCount="indefinite"/></path>'
    )
    add('<path d="M-4,-1 L-19,13 L-19,16 L-4,10Z" fill="#8B949E"/>')
    add('<path d="M4,-1 L19,13 L19,16 L4,10Z" fill="#8B949E"/>')
    add('<path d="M-9,5 L-17,13 L-17,14.5 L-9,7.5Z" fill="#00B84F"/>')
    add('<path d="M9,5 L17,13 L17,14.5 L9,7.5Z" fill="#00B84F"/>')
    add('<rect x="-19.5" y="8" width="1.8" height="10" rx=".5" fill="#39D353"/>')
    add('<rect x="17.7" y="8" width="1.8" height="10" rx=".5" fill="#39D353"/>')
    add('<path d="M0,-19 L5,-5 L5,11 L-5,11 L-5,-5Z" fill="#C9D1D9"/>')
    add('<path d="M0,-12 L2.8,-5 L-2.8,-5Z" fill="#0B3D2E" stroke="#39D353" stroke-width=".8"/>')
    add('<rect x="-1.2" y="1" width="2.4" height="8" rx="1" fill="#00B84F"/>')
    add("</g>")

    add("</svg>")
    return "\n".join(out), len(targets_by_col), sum(len(v) for v in targets_by_col.values())


def main():
    output = os.environ.get("OUTPUT", "assets/contribution-fighter.svg")
    if os.environ.get("DEMO") == "1":
        weeks = demo_weeks()
    else:
        token, user = os.environ.get("GH_TOKEN"), os.environ.get("GH_USER")
        if not token or not user:
            sys.exit("Faltan GH_TOKEN y GH_USER (o usa DEMO=1).")
        weeks = fetch_weeks(user, token)

    svg, cols, cells = build_svg(weeks)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{output}: {len(weeks)} semanas, {cols} columnas con disparos, {cells} blancos")


if __name__ == "__main__":
    main()
