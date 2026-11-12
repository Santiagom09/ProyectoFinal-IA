"""Grafo multimodal del Valle de Aburrá (MVP offline).
Nodos: estaciones de la Línea A del Metro (coordenadas APROXIMADAS: verificar).
Aristas: metro (estaciones consecutivas) + bus/bici/carro entre nodos a <= 8 km.
Parámetros de velocidad, costo y emisiones son SUPUESTOS editables (citar fuente en el informe).
"""

import math, unicodedata, json, os

STATIONS = [
    ("Niquía", 6.3371, -75.5445),
    ("Bello", 6.3329, -75.5540),
    ("Madera", 6.3224, -75.5560),
    ("Acevedo", 6.2998, -75.5590),
    ("Tricentenario", 6.2900, -75.5663),
    ("Caribe", 6.2779, -75.5688),
    ("Universidad", 6.2677, -75.5662),
    ("Hospital", 6.2610, -75.5643),
    ("Prado", 6.2567, -75.5636),
    ("Parque Berrío", 6.2517, -75.5679),
    ("San Antonio", 6.2475, -75.5680),
    ("Alpujarra", 6.2430, -75.5700),
    ("Exposiciones", 6.2335, -75.5700),
    ("Industriales", 6.2290, -75.5737),
    ("Poblado", 6.2125, -75.5780),
    ("Aguacatala", 6.1985, -75.5790),
    ("Ayurá", 6.1830, -75.5855),
    ("Envigado", 6.1750, -75.5875),
    ("Itagüí", 6.1665, -75.6050),
    ("Sabaneta", 6.1520, -75.6160),
    ("La Estrella", 6.1380, -75.6270),
]
NAMES = [s[0] for s in STATIONS]
COORD = {n: (la, lo) for n, la, lo in STATIONS}

METRO_LINES = {
    "A": {
        "nombre": "Línea A",
        "terminales": ("Niquía", "La Estrella"),
        "estaciones": NAMES,
    }
}
METRO_HOURS = {
    "lun-sab": (4.5, 23.0),
    "dom-fest": (5.0, 22.0),
}  # fuente: ver corpus/metro_medellin.md


def day_type(d):
    try:
        import holidays

        if d in holidays.Colombia():
            return "dom-fest"
    except Exception:
        pass
    return "dom-fest" if d.weekday() == 6 else "lun-sab"


def metro_status(hour, dtype="lun-sab"):
    a, b = METRO_HOURS[dtype]
    t = hour + 0.5  # se evalúa a mitad de la hora elegida
    f = lambda x: f"{int(x)}:{int(round((x%1)*60)):02d}"
    return {
        "abierto": a <= t <= b,
        "horario": f"{f(a)}–{f(b)}",
        "tipo_dia": dtype,
        "linea": "Línea A (Niquía – La Estrella)",
        "nota": "Horario regular; hay ampliaciones y cierres especiales (verificar en metrodemedellin.gov.co).",
    }


_p = os.path.join(os.path.dirname(__file__), "..", "data", "bus_routes.json")
BUS_ROUTES = json.load(open(_p, encoding="utf-8")) if os.path.exists(_p) else []

# speed km/h (flujo libre), COP/km, gCO2/km, factor de distancia sobre línea recta
MODES = {
    "metro": {"speed": 35, "cop_km": 350, "co2_km": 30, "detour": 1.1},
    "bus": {"speed": 22, "cop_km": 450, "co2_km": 80, "detour": 1.3},
    "bici": {"speed": 15, "cop_km": 0, "co2_km": 0, "detour": 1.3},
    "carro": {"speed": 40, "cop_km": 1200, "co2_km": 170, "detour": 1.3},
}


def norm(s):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


def resolve(name):
    for n in NAMES:
        if norm(n) == norm(name):
            return n
    for n in NAMES:
        if norm(name) in norm(n):
            return n
    raise ValueError(f"Estación desconocida: '{name}'. Opciones: {', '.join(NAMES)}")


def haversine(a, b):
    (la1, lo1), (la2, lo2) = COORD[a], COORD[b]
    p = math.pi / 180
    x = (
        math.sin((la2 - la1) * p / 2) ** 2
        + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    )
    return 12742 * math.asin(math.sqrt(x))


def build_graph(k=3):
    """Metro: estaciones consecutivas. Bus: solo tramos entre paradas de cada ruta (data/bus_routes.json).
    Bici/carro: solo k vecinos más cercanos (evita 'cuerdas' largas en línea recta)."""
    adj = {n: [] for n in NAMES}

    def add(a, b, m, r=""):
        adj[a].append((b, m, haversine(a, b) * MODES[m]["detour"], r))

    for i, a in enumerate(NAMES):
        if i + 1 < len(NAMES):
            add(a, NAMES[i + 1], "metro", "A")
            add(NAMES[i + 1], a, "metro", "A")
    pairs = set()
    for a in NAMES:
        for b in sorted((x for x in NAMES if x != a), key=lambda x: haversine(a, x))[
            :k
        ]:
            pairs.add(frozenset((a, b)))
    for p in pairs:
        a, b = tuple(p)
        for m in ("bici", "carro"):
            add(a, b, m)
            add(b, a, m)
    for r in BUS_ROUTES:
        st = [x for x in r["paradas"] if x in COORD]
        for a, b in zip(st, st[1:]):
            add(a, b, "bus", r["id"])
            add(b, a, "bus", r["id"])
    return adj


def congestion(mode, hour):
    peak = (6 <= hour < 9) or (17 <= hour < 20)
    return {"carro": 0.5, "bus": 0.6}.get(mode, 1.0) if peak else 1.0


def edge_metrics(mode, dist, hour):
    m = MODES[mode]
    t = dist / (m["speed"] * congestion(mode, hour)) * 60
    return {"min": t, "cop": dist * m["cop_km"], "co2": dist * m["co2_km"], "km": dist}


def scalar_cost(met, w):  # unidades: min, miles COP, 100 g CO2
    return w[0] * met["min"] + w[1] * met["cop"] / 1000 + w[2] * met["co2"] / 100
