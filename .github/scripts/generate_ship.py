#!/usr/bin/env python3
"""
Genera assets/contribution-fighter.svg

Una nave recorre tu gráfica de contribuciones de GitHub y destruye, de uno en uno,
cada día en el que hiciste commits: un disparo por blanco, alternando cañones,
con impacto y explosión. Usa SMIL (animación dentro del SVG), así que funciona
dentro de un README sin JavaScript.

Variables de entorno:
  GH_TOKEN   token de GitHub (obligatorio, salvo con DEMO=1)
  GH_USER    usuario de GitHub (obligatorio, salvo con DEMO=1)
  OUTPUT     ruta de salida (por defecto assets/contribution-fighter.svg)
  DEMO=1     usa datos aleatorios, útil para probar sin token
"""
import json
import math
import os
import random
import sys
import urllib.request

# --------------------------------------------------------------------------- #
# Configuración visual y de ritmo
# --------------------------------------------------------------------------- #
CELL, GAP = 11, 3
PITCH = CELL + GAP
ROWS = 7
PAD_X, PAD_TOP = 24, 26

INTRO = 0.9            # s que tarda la nave en entrar
FIRE_TARGET = 10.0     # s aprox. que dura toda la ráfaga de disparos
DT_MIN, DT_MAX = 0.035, 0.07  # intervalo entre disparos (s)
BOLT_SPEED = 650.0     # px/s
MOVE_BASE = 0.07       # s para pasar a la siguiente columna
MOVE_PER_COL = 0.01    # s extra por cada columna que se salta
CANNON_X = 18.6        # separación de los cañones respecto al centro de la nave

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
    return [
        [(d, rnd.choices([0, 1, 2, 3, 4], [38, 24, 18, 12, 8])[0]) for d in range(7)]
        for _ in range(n)
    ]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def f(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def kt(times, total):
    """keyTimes normalizados; exige que sean estrictamente crecientes."""
    norm = [round(t / total, 6) for t in times]
    assert norm[0] == 0 and norm[-1] == 1, norm
    assert all(a < b for a, b in zip(norm, norm[1:])), f"keyTimes no crecientes: {times}"
    return ";".join(f"{v:.6f}".rstrip("0").rstrip(".") or "0" for v in norm)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# --------------------------------------------------------------------------- #
# Planeación de la secuencia (qué se dispara, cuándo y desde dónde)
# --------------------------------------------------------------------------- #
def plan(weeks):
    n = len(weeks)
    width = PAD_X * 2 + n * PITCH - GAP
    grid_bottom = PAD_TOP + ROWS * PITCH - GAP
    ship_y = grid_bottom + 50
    height = ship_y + 30

    def col_x(c):
        return PAD_X + c * PITCH + CELL / 2

    targets = {}
    for c, week in enumerate(weeks):
        cells = sorted([(wd, lv) for wd, lv in week if lv > 0], key=lambda t: -t[0])  # de abajo hacia arriba
        if cells:
            targets[c] = cells
    cols = sorted(targets)
    total_shots = sum(len(v) for v in targets.values())
    dt = clamp(FIRE_TARGET / max(total_shots, 1), DT_MIN, DT_MAX)

    ship_kf = [(0.0, -60.0)]   # (tiempo, x)
    rot_kf = [(0.0, 0.0)]      # (tiempo, grados)
    shots = []
    cur = INTRO
    k = 0
    exit_end = INTRO

    for i, c in enumerate(cols):
        x = col_x(c)
        arrive = cur
        ship_kf.append((arrive, x))
        rot_kf.append((arrive, 0.0))
        for wd, lv in targets[c]:
            side = -1 if k % 2 == 0 else 1
            sx, sy = x + side * CANNON_X, ship_y + 8
            tx, ty = x, PAD_TOP + wd * PITCH + CELL / 2
            fire = cur
            hit = fire + math.hypot(tx - sx, ty - sy) / BOLT_SPEED
            shots.append(
                dict(fire=fire, hit=hit, side=side, sx=sx, sy=sy, tx=tx, ty=ty,
                     col=c, row=wd, level=lv,
                     angle=math.degrees(math.atan2(ty - sy, tx - sx)))
            )
            cur += dt
            k += 1
        hold_end = cur - dt + 0.02
        ship_kf.append((hold_end, x))
        rot_kf.append((hold_end, 0.0))
        if i + 1 < len(cols):
            gap = cols[i + 1] - c
            move = MOVE_BASE + MOVE_PER_COL * (gap - 1)
            rot_kf.append((hold_end + move / 2, 9.0))
            cur = hold_end + move
        else:
            exit_end = hold_end + 0.9
            ship_kf.append((exit_end, width + 60.0))
            rot_kf.append((hold_end + 0.45, 11.0))
            rot_kf.append((exit_end, 11.0))

    last_hit = max((s["hit"] for s in shots), default=INTRO)
    total = max(exit_end, last_hit) + 0.5 + 1.0
    if not shots:  # perfil sin actividad: la nave solo cruza la pantalla
        ship_kf = [(0.0, -60.0), (INTRO, width / 2), (INTRO + 1.5, width + 60.0)]
        rot_kf = [(0.0, 0.0), (INTRO + 1.5, 0.0)]
        total = INTRO + 3.0
    ship_kf.append((total, ship_kf[-1][1]))
    rot_kf.append((total, rot_kf[-1][1]))

    return dict(width=width, height=height, ship_y=ship_y, total=total, dt=dt,
                ship_kf=ship_kf, rot_kf=rot_kf, shots=shots, weeks=weeks)


# --------------------------------------------------------------------------- #
# Dibujo
# --------------------------------------------------------------------------- #
def star_markup(width, height):
    rnd = random.Random(21)
    parts = []
    for _ in range(45):
        sx, sy = rnd.uniform(6, width - 6), rnd.uniform(0, height)
        r = rnd.choice([0.5, 0.6, 0.8, 1.0])
        op = rnd.uniform(0.25, 0.7)
        parts.append(f'<circle cx="{f(sx)}" cy="{f(sy)}" r="{r}" fill="#C9D1D9" opacity="{f(op)}"/>')
    return "".join(parts)


def build_svg(weeks):
    p = plan(weeks)
    W, H, ship_y, T = p["width"], p["height"], p["ship_y"], p["total"]
    out = []
    add = out.append

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Nave espacial destruyendo la gráfica de contribuciones">'
    )
    add(
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0D1117"/><stop offset="1" stop-color="#0B1F17"/></linearGradient>'
        '<linearGradient id="bolt" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#39D353" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#D9FFE3"/></linearGradient>'
        '</defs>'
    )
    add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="url(#bg)" stroke="#30363D"/>')

    # Estrellas que bajan: da sensación de velocidad
    stars = star_markup(W, H)
    add(
        f'<g>{stars}<animateTransform attributeName="transform" type="translate" '
        f'values="0,0;0,{H}" dur="5s" repeatCount="indefinite"/></g>'
    )
    add(
        f'<g transform="translate(0 {-H})">{stars}<animateTransform attributeName="transform" type="translate" '
        f'values="0,{-H};0,0" dur="5s" repeatCount="indefinite"/></g>'
    )

    # Celdas vacías (no se destruyen)
    for c, week in enumerate(weeks):
        for wd, lv in week:
            if lv == 0:
                add(f'<rect x="{PAD_X + c * PITCH}" y="{PAD_TOP + wd * PITCH}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS[0]}"/>')

    # Celdas con actividad + impacto + proyectil (uno por blanco)
    for s in p["shots"]:
        x, y = PAD_X + s["col"] * PITCH, PAD_TOP + s["row"] * PITCH
        th, fire = s["hit"], s["fire"]
        # Celda
        add(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS[s["level"]]}">'
            f'<animate attributeName="opacity" values="1;1;0;0;1" '
            f'keyTimes="{kt([0, th, th + 0.08, T - 1.0, T], T)}" dur="{f(T)}s" repeatCount="indefinite"/></rect>'
        )
        cx, cy = s["tx"], s["ty"]
        # Anillo de explosión
        ke = kt([0, th - 0.002, th, th + 0.4, T], T)
        add(
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="0" fill="none" stroke="#7CFFA0" stroke-width="1.2" opacity="0">'
            f'<animate attributeName="r" values="0;0;1;9;9" keyTimes="{ke}" dur="{f(T)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;.9;0;0" keyTimes="{ke}" dur="{f(T)}s" repeatCount="indefinite"/></circle>'
        )
        # Destello central
        kc = kt([0, th - 0.002, th, th + 0.16, T], T)
        add(
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="3.5" fill="#E6FFEC" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{kc}" dur="{f(T)}s" repeatCount="indefinite"/></circle>'
        )
        # Proyectil
        kb_pos = kt([0, fire, th, T], T)
        kb_op = kt([0, fire - 0.002, fire, th, th + 0.002, T], T)
        a, b = f'{f(s["sx"])},{f(s["sy"])}', f'{f(s["tx"])},{f(s["ty"])}'
        add(
            f'<g transform="translate({f(s["sx"])} {f(s["sy"])})" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" values="{a};{a};{b};{b}" '
            f'keyTimes="{kb_pos}" dur="{f(T)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kb_op}" dur="{f(T)}s" repeatCount="indefinite"/>'
            f'<g transform="rotate({f(s["angle"])})"><rect x="-11" y="-1.1" width="11" height="2.2" rx="1.1" fill="url(#bolt)"/></g></g>'
        )

    # Nave: grupo exterior = posición, grupo interior = inclinación al desplazarse
    ship_vals = ";".join(f"{f(x)},{ship_y}" for _, x in p["ship_kf"])
    rot_vals = ";".join(f(a) for _, a in p["rot_kf"])
    add(f'<g transform="translate({f(p["ship_kf"][0][1])} {ship_y})">')
    add(
        f'<animateTransform attributeName="transform" type="translate" values="{ship_vals}" '
        f'keyTimes="{kt([t for t, _ in p["ship_kf"]], T)}" dur="{f(T)}s" repeatCount="indefinite"/>'
    )
    add("<g>")
    add(
        f'<animateTransform attributeName="transform" type="rotate" values="{rot_vals}" '
        f'keyTimes="{kt([t for t, _ in p["rot_kf"]], T)}" dur="{f(T)}s" repeatCount="indefinite"/>'
    )
    add(
        '<path d="M-3,10 L0,19 L3,10Z" fill="#39D353">'
        '<animate attributeName="opacity" values="1;.45;1" dur=".2s" repeatCount="indefinite"/></path>'
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
    # Destellos en los cañones, sincronizados con cada disparo
    for side in (-1, 1):
        times = [s["fire"] for s in p["shots"] if s["side"] == side]
        if not times:
            continue
        kts, vals = [0.0], ["0"]
        for t in times:
            kts += [t - 0.002, t, t + 0.05]
            vals += ["0", "1", "0"]
        kts.append(T)
        vals.append("0")
        add(
            f'<circle cx="{f(side * CANNON_X)}" cy="7" r="3.2" fill="#E6FFEC" opacity="0">'
            f'<animate attributeName="opacity" values="{";".join(vals)}" keyTimes="{kt(kts, T)}" '
            f'dur="{f(T)}s" repeatCount="indefinite"/></circle>'
        )
    add("</g></g>")
    add("</svg>")

    return "\n".join(out), p


def main():
    output = os.environ.get("OUTPUT", "assets/contribution-fighter.svg")
    if os.environ.get("DEMO") == "1":
        weeks = demo_weeks()
    else:
        token, user = os.environ.get("GH_TOKEN"), os.environ.get("GH_USER")
        if not token or not user:
            sys.exit("Faltan GH_TOKEN y GH_USER (o usa DEMO=1).")
        weeks = fetch_weeks(user, token)

    svg, p = build_svg(weeks)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(
        f"{output}: {len(weeks)} semanas, {len(p['shots'])} disparos, "
        f"{p['dt'] * 1000:.0f} ms entre disparos, ciclo de {p['total']:.1f} s, {len(svg) // 1024} KB"
    )


if __name__ == "__main__":
    main()
