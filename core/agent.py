"""Loop agéntico manual con tool calling (endpoint compatible con OpenAI). T_max acotado."""

import json, os, re, time
from dotenv import load_dotenv
from openai import OpenAI
from .graph import resolve, MODES, metro_status, METRO_LINES, NAMES
from .search import astar, graph, legs
from .rag import Retriever

load_dotenv()
T_MAX = 6
_R = Retriever()


def get_metro_status(hour=8, tipo_dia="lun-sab"):
    return metro_status(int(hour), tipo_dia) | {"estaciones": NAMES}


def plan_route(
    origin,
    destination,
    hour=8,
    tipo_dia="lun-sab",
    w_time=1.0,
    w_cost=0.3,
    w_co2=0.3,
    modes=None,
):
    modes = list(modes or MODES)
    o, d = resolve(origin), resolve(destination)
    aviso = None
    if "metro" in modes and not metro_status(int(hour), tipo_dia)["abierto"]:
        modes.remove("metro")
        aviso = "El Metro está cerrado a esa hora; se excluyó."
    r = astar(graph(), o, d, int(hour), (w_time, w_cost, w_co2), modes)
    if not r["found"]:
        return {"error": "No hay ruta con esos modos.", "aviso": aviso}
    return {
        "aviso": aviso,
        "tramos": [
            {
                "modo": L["mode"],
                "linea_o_ruta": L["route"],
                "paradas": L["stops"],
                "minutos": round(L["min"], 1),
            }
            for L in legs(r["edges"])
        ],
        "minutos": round(r["totals"]["min"], 1),
        "cop": round(r["totals"]["cop"]),
        "gCO2": round(r["totals"]["co2"]),
        "nodos_expandidos": r["expanded"],
    }


PYP = {
    "lunes": (5, 8),
    "martes": (1, 4),
    "miercoles": (0, 2),
    "jueves": (3, 6),
    "viernes": (7, 9),
}


def check_pico_y_placa(ultimo_digito, dia, hora=None):
    """Regla del Decreto 1490/2026 (Medellín, 2.º semestre 2026, carros particulares y motos)."""
    d = dia.lower().replace("é", "e").replace("á", "a")
    if d in ("sabado", "domingo"):
        return {
            "restringido": False,
            "motivo": "Fin de semana: sin pico y placa.",
            "fuente": "pico_y_placa.md",
        }
    if d not in PYP:
        return {"error": f"Día no válido: {dia}"}
    en_dia = int(ultimo_digito) in PYP[d]
    en_hora = hora is None or 5 <= int(hora) < 20
    return {
        "restringido": en_dia and en_hora,
        "digitos_ese_dia": list(PYP[d]),
        "horario": "05:00-20:00",
        "nota": "Aplica a carros particulares (último dígito) y motos (primer dígito); verificar exenciones y vías exentas.",
        "fuente": "pico_y_placa.md (Decreto 1490 de 2026)",
    }


def search_docs(query):
    r = _R.search(
        query, k=2
    )  # k=2 y texto recortado: ahorra tokens (límite TPM del plan gratuito)
    return [{**x, "text": x["text"][:600]} for x in r] or [
        {"error": "Sin resultados en el corpus."}
    ]


def _chat(client, msgs, intentos=5):
    """Llama al LLM; ante error 429 (límite de tokens/min) espera y reintenta."""
    for i in range(intentos):
        try:
            return (
                client.chat.completions.create(
                    model=os.getenv("LLM_MODEL"), messages=msgs, tools=TOOLS
                )
                .choices[0]
                .message
            )
        except Exception as e:
            if "429" not in str(e) or i == intentos - 1:
                raise
            m = re.search(r"try again in ([\d.]+)s", str(e))
            time.sleep(float(m.group(1)) + 2 if m else 10 * (i + 1))


_P = lambda **k: {"type": "object", "properties": k["p"], "required": k.get("r", [])}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "plan_route",
            "description": "Ruta óptima (A*) entre dos estaciones: devuelve tramos con modo, línea/ruta y paradas.",
            "parameters": _P(
                p={
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "hour": {"type": "integer", "description": "hora 0-23"},
                    "tipo_dia": {"type": "string", "enum": ["lun-sab", "dom-fest"]},
                    "w_time": {"type": "number"},
                    "w_cost": {"type": "number"},
                    "w_co2": {"type": "number"},
                    "modes": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(MODES)},
                    },
                },
                r=["origin", "destination"],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metro_status",
            "description": "Dice si el Metro (Línea A) está en operación a una hora y tipo de día, y su horario.",
            "parameters": _P(
                p={
                    "hour": {"type": "integer"},
                    "tipo_dia": {"type": "string", "enum": ["lun-sab", "dom-fest"]},
                }
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_pico_y_placa",
            "description": "Dice si un vehículo particular tiene pico y placa en Medellín según el dígito de placa, el día y la hora.",
            "parameters": _P(
                p={
                    "ultimo_digito": {"type": "integer"},
                    "dia": {"type": "string", "description": "lunes..domingo"},
                    "hora": {"type": "integer"},
                },
                r=["ultimo_digito", "dia"],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Busca en el corpus (pico y placa, Metro, emisiones). Úsala para reglas y normativa.",
            "parameters": _P(p={"query": {"type": "string"}}, r=["query"]),
        },
    },
]
FUNCS = {
    "plan_route": plan_route,
    "search_docs": search_docs,
    "get_metro_status": get_metro_status,
    "check_pico_y_placa": check_pico_y_placa,
}
SYSTEM = (
    "Eres un copiloto de movilidad del Valle de Aburrá. Responde en español. Para rutas usa plan_route y lista los tramos con sus paradas; "
    "para pico y placa con un dígito concreto usa check_pico_y_placa; para saber si el Metro opera usa get_metro_status; para reglas (pico y placa, Metro, emisiones) usa search_docs y cita la fuente como [archivo]. "
    "Las rutas de bus del MVP pueden ser de ejemplo: avísalo si la ruta incluye bus. No inventes normas. No es asesoría legal."
)


def run_agent(history, user_msg):
    if not os.getenv("LLM_API_KEY"):
        return "Configura LLM_API_KEY en .env para usar el agente.", []
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY")
    )
    msgs = (
        [{"role": "system", "content": SYSTEM}]
        + history
        + [{"role": "user", "content": user_msg}]
    )
    trace = []
    for _ in range(T_MAX):
        try:
            out = _chat(client, msgs)
        except Exception as e:
            return f"Error del LLM: {e}", trace
        if not out.tool_calls:
            return out.content, trace
        msgs.append(out)
        for tc in out.tool_calls:
            try:
                res = FUNCS[tc.function.name](**json.loads(tc.function.arguments))
            except Exception as e:
                res = {"error": str(e)}
            trace.append(
                {"tool": tc.function.name, "args": tc.function.arguments, "result": res}
            )
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(res, ensure_ascii=False),
                }
            )
    return "Se alcanzó el máximo de pasos (T_max) sin respuesta final.", trace
