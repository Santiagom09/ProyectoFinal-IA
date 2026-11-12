import datetime, streamlit as st, plotly.graph_objects as go, pandas as pd
from core.graph import (
    NAMES,
    COORD,
    MODES,
    METRO_LINES,
    BUS_ROUTES,
    metro_status,
    day_type,
)
from core.search import astar, bfs, graph, legs
from core import roads
from core.agent import run_agent

st.set_page_config(page_title="Copiloto de movilidad – Valle de Aburrá", layout="wide")
st.title("🚇 Copiloto de movilidad del Valle de Aburrá")
st.caption(
    "SI3003 · A* multiobjetivo + agente LLM con RAG. Modelo con supuestos; no es información oficial de tráfico."
)

with st.sidebar:
    st.header("Parámetros")
    o = st.selectbox("Origen", NAMES, index=0)
    d = st.selectbox("Destino", NAMES, index=len(NAMES) - 1)
    hour = st.slider("Hora de salida", 0, 23, 8)
    st.subheader("Importancia")
    w = (
        st.slider("Tiempo", 0.0, 1.0, 1.0),
        st.slider("Costo", 0.0, 1.0, 0.3),
        st.slider("Emisiones", 0.0, 1.0, 0.3),
    )
    modes = st.multiselect("Modos permitidos", list(MODES), default=list(MODES))
    DT = {"lun-sab": "Lunes a sábado", "dom-fest": "Domingo / festivo"}
    dtype = st.selectbox(
        "Tipo de día",
        list(DT),
        index=list(DT).index(day_type(datetime.date.today())),
        format_func=DT.get,
    )
    ms = metro_status(hour, dtype)
    (st.success if ms["abierto"] else st.error)(
        f"🚇 Metro {'EN OPERACIÓN' if ms['abierto'] else 'CERRADO'} · {ms['horario']}"
    )
    st.caption(ms["nota"])
    if "metro" in modes and not ms["abierto"]:
        modes = [m for m in modes if m != "metro"]
        st.warning("Metro excluido: está cerrado a esa hora.")

tab1, tab2, tab3 = st.tabs(["🗺️ Rutas", "📊 A* vs Dijkstra vs BFS", "💬 Agente"])
G = graph()
if not modes:
    st.warning("Selecciona al menos un modo.")
    st.stop()
if o == d:
    st.warning("Origen y destino son iguales.")
    st.stop()

ICON = {"metro": "🚇", "bus": "🚌", "bici": "🚲", "carro": "🚗"}
COLORS = {"metro": "#1f77b4", "bus": "#ff7f0e", "bici": "#2ca02c", "carro": "#d62728"}


def leg_title(L):
    s_ = L["stops"]
    if L["mode"] == "metro":
        t = METRO_LINES[L["route"]]["terminales"]
        return f"Metro {METRO_LINES[L['route']]['nombre']} · dirección {t[1] if NAMES.index(s_[-1])>NAMES.index(s_[0]) else t[0]}"
    return (
        f"Bus {L['route']}"
        if L["mode"] == "bus"
        else {"bici": "Bicicleta", "carro": "Carro"}[L["mode"]]
    )


def leg_coords(L):
    pts = []
    for a, b in zip(L["stops"], L["stops"][1:]):
        seg = (
            roads.segment(COORD[a], COORD[b])
            if L["mode"] != "metro"
            else [COORD[a], COORD[b]]
        )
        pts += seg if not pts else seg[1:]
    return pts


with tab1:
    opts = {"Óptima (mixta)": astar(G, o, d, hour, w, modes)}
    for m in modes:
        opts[f"Solo {m}"] = astar(G, o, d, hour, w, [m])
    best = opts["Óptima (mixta)"]
    fig = go.Figure(
        go.Scattermap(
            lat=[COORD[n][0] for n in NAMES],
            lon=[COORD[n][1] for n in NAMES],
            mode="markers",
            marker=dict(size=6, color="gray"),
            text=NAMES,
            hoverinfo="text",
            name="Estaciones",
        )
    )
    plan = legs(best["edges"]) if best["found"] else []
    for L in plan:
        pts = leg_coords(L)
        fig.add_trace(
            go.Scattermap(
                lat=[p[0] for p in pts],
                lon=[p[1] for p in pts],
                mode="lines",
                line=dict(width=5, color=COLORS[L["mode"]]),
                name=f"{ICON[L['mode']]} {leg_title(L)}",
                hoverinfo="name",
            )
        )
        fig.add_trace(
            go.Scattermap(
                lat=[COORD[x][0] for x in L["stops"]],
                lon=[COORD[x][1] for x in L["stops"]],
                mode="markers",
                marker=dict(size=9, color=COLORS[L["mode"]]),
                text=L["stops"],
                hoverinfo="text",
                showlegend=False,
            )
        )
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=6.24, lon=-75.58), zoom=10),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        legend=dict(orientation="h", y=1.02),
    )
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(fig, width="stretch")
        if not roads.available():
            st.caption(
                "Trazado en línea recta entre paradas. Para seguir las calles reales: ver README (OSM opcional)."
            )
    with c2:
        st.subheader("Itinerario")
        if not plan:
            st.error("No hay ruta con los modos y la hora elegidos.")
        for n, L in enumerate(plan, 1):
            st.markdown(
                f"**{n}. {ICON[L['mode']]} {leg_title(L)}** — {L['min']:.0f} min · {L['km']:.1f} km · ${L['cop']:,.0f}"
            )
            st.markdown(
                "  \n".join(
                    [f"● **{L['stops'][0]}** (sube)"]
                    + [f"│ {x}" for x in L["stops"][1:-1]]
                    + [f"● **{L['stops'][-1]}** (baja)"]
                )
            )
        if any(L["mode"] == "bus" for L in plan) and any(
            r.get("ilustrativa") for r in BUS_ROUTES
        ):
            st.info(
                "⚠️ Las rutas de bus son de EJEMPLO. Reemplazar `data/bus_routes.json` con datos reales (GTFS / MEData)."
            )
    rows = [
        {
            "Opción": k,
            "Minutos": round(r["totals"]["min"], 1),
            "Costo COP": round(r["totals"]["cop"]),
            "gCO2": round(r["totals"]["co2"]),
            "Tramos": len(r["edges"]),
            "Costo ponderado": round(r["cost"], 2),
        }
        for k, r in opts.items()
        if r["found"]
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("🚇 Línea A del Metro: recorrido y estado"):
        A = METRO_LINES["A"]
        used = {x for L in plan if L["mode"] == "metro" for x in L["stops"]}
        st.write(
            f"**{A['nombre']}** · {A['terminales'][0]} ⇄ {A['terminales'][1]} · {ms['horario']} · {'🟢 en operación' if ms['abierto'] else '🔴 cerrado'}"
        )
        st.markdown(
            "  \n".join(
                ("● **" + x + "** ← en tu ruta") if x in used else "│ " + x
                for x in A["estaciones"]
            )
        )

with tab2:
    a = astar(G, o, d, hour, w, modes)
    u = astar(G, o, d, hour, w, modes, use_h=False)
    b = bfs(G, o, d, hour, w, modes)
    df = pd.DataFrame(
        {
            "Algoritmo": ["A*", "Dijkstra", "BFS"],
            "Nodos expandidos": [a["expanded"], u["expanded"], b["expanded"]],
            "Costo ponderado": [
                round(a["cost"], 2),
                round(u["cost"], 2),
                round(b["cost"], 2),
            ],
        }
    )
    st.plotly_chart(
        go.Figure(go.Bar(x=df["Algoritmo"], y=df["Nodos expandidos"])).update_layout(
            title="Nodos expandidos", height=350
        ),
        width="stretch",
    )
    st.dataframe(df, hide_index=True)
    st.caption(
        "BFS minimiza número de tramos, no costo. Evaluación sobre todos los pares: `python eval/benchmark_search.py`."
    )

with tab3:
    st.session_state.setdefault("chat", [])
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if q := st.chat_input(
        "Ej: ¿Cómo voy de Poblado a Niquía a las 7 am con el menor CO2?"
    ):
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                ans, trace = run_agent(
                    [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat
                    ],
                    q,
                )
            st.markdown(ans)
            if trace:
                with st.expander("Herramientas llamadas"):
                    st.json(trace)
        st.session_state.chat += [
            {"role": "user", "content": q},
            {"role": "assistant", "content": ans},
        ]
