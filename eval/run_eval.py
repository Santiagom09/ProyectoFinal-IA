"""Evalúa el agente con preguntas fijas: ¿llamó a la herramienta correcta? ¿citó la fuente?
Uso:  python eval/run_eval.py      (requiere LLM_API_KEY en .env)   ->  eval/resultados.csv y eval/resultados.md
"""

import json, os, sys, time, csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
HERE = os.path.dirname(__file__)


def evaluar(run_agent, pausa=8.0):
    preguntas = json.load(open(os.path.join(HERE, "preguntas.json"), encoding="utf-8"))
    filas = []
    for q in preguntas:
        ans, trace = run_agent([], q["pregunta"])
        if (ans or "").startswith(("Error del LLM", "Configura LLM_API_KEY")):
            raise SystemExit(
                f"\nEvaluación detenida en la pregunta {q['id']}: {ans}\nCorrige LLM_MODEL / LLM_API_KEY en .env (ver scripts/listar_modelos.py) y vuelve a correr."
            )
        llamadas = [t["tool"] for t in trace]
        esperadas = q["herramientas"]
        tool_ok = (
            (not llamadas) if not esperadas else all(e in llamadas for e in esperadas)
        )
        txt = (ans or "").lower()
        cita_ok = "n/a" if not q["cita"] else any(c in txt for c in q["cita"])
        filas.append(
            {
                "id": q["id"],
                "pregunta": q["pregunta"],
                "esperadas": "+".join(esperadas) or "ninguna",
                "llamadas": "+".join(llamadas) or "ninguna",
                "herramienta_ok": tool_ok,
                "cita_fuente": cita_ok,
                "respuesta": (ans or "").replace("\n", " ")[:300],
                "nota": q.get("nota", ""),
            }
        )
        print(f'[{q["id"]:>2}] tool_ok={tool_ok} cita={cita_ok} llamadas={llamadas}')
        time.sleep(pausa)
    return filas


def guardar(filas):
    with open(
        os.path.join(HERE, "resultados.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    n = len(filas)
    ok = sum(r["herramienta_ok"] for r in filas)
    citables = [r for r in filas if r["cita_fuente"] != "n/a"]
    cok = sum(r["cita_fuente"] is True for r in citables)
    md = [
        "| # | Pregunta | Esperada | Llamó | Herr. OK | Citó |",
        "|---|---|---|---|---|---|",
    ]
    md += [
        f'| {r["id"]} | {r["pregunta"]} | {r["esperadas"]} | {r["llamadas"]} | {"✅" if r["herramienta_ok"] else "❌"} | {r["cita_fuente"]} |'
        for r in filas
    ]
    md += [
        "",
        f"**Herramienta correcta: {ok}/{n} ({100*ok/n:.0f}%).** Citó la fuente: {cok}/{len(citables)} de las preguntas que lo requieren.",
    ]
    open(os.path.join(HERE, "resultados.md"), "w", encoding="utf-8").write(
        "\n".join(md)
    )
    print("\n".join(md[-1:]))


if __name__ == "__main__":
    from core.agent import run_agent

    guardar(evaluar(run_agent))
