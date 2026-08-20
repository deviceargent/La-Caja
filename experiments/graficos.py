"""Graficos de barras de la evidencia final (La Caja).

Lee los JSONs canonicos de experiments/results/ y dibuja las figuras que
se referencian en el README. No inventa numeros: cada barra sale de un
resultado real pre-registrado.

Uso:
  python experiments/graficos.py

Salida: docs/figures/*.png
"""

import json
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTADOS = os.path.join(RAIZ, "experiments", "results")
SALIDA = os.path.join(RAIZ, "docs", "figures")


def _cargar(nombre):
    with open(os.path.join(RESULTADOS, nombre), encoding="utf-8") as fh:
        return json.load(fh)


def _barras(datos, nombres, colores, titulo, ylabel, figura, decimales=3, anotar=None):
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(datos))
    ax.bar(x, datos, color=colores, edgecolor="black", linewidth=0.6, width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(nombres, rotation=0, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(titulo, fontsize=10, fontweight="bold")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for i, v in enumerate(datos):
        etiqueta = anotar[i] if anotar else f"{v:.{decimales}f}"
        ax.text(i, v + max(datos) * 0.02, etiqueta, ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, figura), dpi=150)
    plt.close(fig)
    print(f"  -> {figura}")


def _resumen_2x2(pareado, cloze, dormidos, primado, rehidratacion):
    fig, ejes = plt.subplots(2, 2, figsize=(10, 6.5))

    # La tesis (pareado): recall con vs sin
    ax = ejes[0, 0]
    v = [pareado["recall_medio_con"], pareado["recall_medio_sin"]]
    ax.bar([0, 1], v, color=["#2e7d32", "#c62828"], edgecolor="black", width=0.55, linewidth=0.6)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["con La Caja", "sin La Caja"], fontsize=8)
    ax.set_title(f"Tesis: recall (win_rate {pareado['win_rate']})", fontsize=9, fontweight="bold")
    ax.set_ylabel("recall medio", fontsize=8)
    for i, val in enumerate(v):
        ax.text(i, val + max(v) * 0.02, f"{val:.4f}", ha="center", fontsize=7)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    # Cloze (FALSA): frecuencia gana
    ax = ejes[0, 1]
    v = [cloze["modelo+memoria"], cloze["modelo_sin_memoria"], cloze["frecuencia"]]
    ax.bar([0, 1, 2], v, color=["#c62828", "#c62828", "#1565c0"], edgecolor="black", width=0.55, linewidth=0.6)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["modelo+memoria", "modelo sin", "frecuencia"], fontsize=8, rotation=15, ha="right")
    ax.set_title("Cloze: reordenar memoria (FALSA)", fontsize=9, fontweight="bold")
    ax.set_ylabel("hit@5", fontsize=8)
    for i, val in enumerate(v):
        ax.text(i, val + max(v) * 0.02, f"{val:.3f}", ha="center", fontsize=7)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    # Traza dormida (FALSA): no predice
    ax = ejes[1, 0]
    v = [dormidos["modelo+traza"], dormidos["modelo_sin_memoria"], dormidos["frecuencia"]]
    ax.bar([0, 1, 2], v, color=["#c62828", "#c62828", "#1565c0"], edgecolor="black", width=0.55, linewidth=0.6)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["modelo+traza", "modelo sin", "frecuencia"], fontsize=8, rotation=15, ha="right")
    ax.set_title("Traza dormida predice el futuro (FALSA)", fontsize=9, fontweight="bold")
    ax.set_ylabel("hit@5", fontsize=8)
    for i, val in enumerate(v):
        ax.text(i, val + max(v) * 0.02, f"{val:.3f}", ha="center", fontsize=7)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    # Primado (ok): modelo vs frecuencia vs aleatorio
    ax = ejes[1, 1]
    v = [primado["hit5_modelo"], primado["hit5_frecuencia"], primado["hit5_aleatorio"]]
    ax.bar([0, 1, 2], v, color=["#2e7d32", "#1565c0", "#9e9e9e"], edgecolor="black", width=0.55, linewidth=0.6)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["modelo (primado)", "frecuencia", "aleatorio"], fontsize=8, rotation=15, ha="right")
    ax.set_title("Recuperación temporal (C1/C2, ok)", fontsize=9, fontweight="bold")
    ax.set_ylabel("hit@5", fontsize=8)
    for i, val in enumerate(v):
        ax.text(i, val + max(v) * 0.02, f"{val:.4f}", ha="center", fontsize=7)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    fig.suptitle("La Caja — evidencia final (Enron, gpt-4o-mini)", fontsize=11, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(SALIDA, "resumen_evidencia.png"), dpi=150)
    plt.close(fig)
    print("  -> resumen_evidencia.png")

    # Rehidratacion: comparar 1-6m base vs rehidratado (enron)
    base = primado["hit5_por_vacio"]["1-6m"]["hit5_modelo"]
    reh = rehidratacion["test_c"]["hit5_por_vacio"]["1-6m"]["hit5_modelo"]
    v = [base, reh]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar([0, 1], v, color=["#546e7a", "#2e7d32"], edgecolor="black", width=0.55, linewidth=0.6)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["base", "rehidratado"], fontsize=9)
    ax.set_title("Rehidratación por re-observación (ventana 1-6m)", fontsize=10, fontweight="bold")
    ax.set_ylabel("hit@5", fontsize=9)
    mejora = (reh - base) / base * 100
    for i, val in enumerate(v):
        ax.text(i, val + max(v) * 0.02, f"{val:.4f}", ha="center", fontsize=8)
    ax.text(0.5, max(v) * 0.75, f"+{mejora:.0f}%", ha="center", fontsize=9, fontweight="bold", color="#2e7d32")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, "rehidratacion.png"), dpi=150)
    plt.close(fig)
    print("  -> rehidratacion.png")


def main():
    pareado = _cargar("eval_pareado_memoria_enron.json")
    cloze = _cargar("eval_modelo_enron.json")
    dormidos = _cargar("eval_dormidos_enron.json")
    enron = _cargar("resultado_enron.json")
    rehidratacion = _cargar("resultado_enron_rehidratar.json")
    primado = enron["test_c"]

    os.makedirs(SALIDA, exist_ok=True)
    print("Generando figuras...")

    # Tesis: barra individual con recall con/sin
    _barras(
        [pareado["recall_medio_con"], pareado["recall_medio_sin"]],
        ["con La Caja", "sin La Caja"],
        ["#2e7d32", "#c62828"],
        "Tesis: La Caja como soporte de memoria (recall medio)",
        "recall medio",
        "tesis_pareada.png",
        anotar=[f"{pareado['recall_medio_con']:.4f}", f"{pareado['recall_medio_sin']:.4f}"],
    )

    # win_rate con p
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(["gana con La Caja", "empate", "gana sin La Caja"],
           [pareado["gana_con"], pareado["empate"], pareado["gana_sin"]],
           color=["#2e7d32", "#9e9e9e", "#c62828"], edgecolor="black", width=0.6, linewidth=0.6)
    ax.set_title(f"Veredictos por consulta (n={pareado['n']}, win_rate {pareado['win_rate']})",
                 fontsize=10, fontweight="bold")
    ax.set_ylabel("consultas", fontsize=9)
    for i, val in enumerate([pareado["gana_con"], pareado["empate"], pareado["gana_sin"]]):
        ax.text(i, val + 3, str(val), ha="center", fontsize=8)
    ax.text(1, 320, f"p = {pareado['p_binominal']:.1e}", ha="center", fontsize=8, color="#2e7d32")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, "tesis_veredictos.png"), dpi=150)
    plt.close(fig)
    print("  -> tesis_veredictos.png")

    _resumen_2x2(pareado, cloze, dormidos, primado, rehidratacion)


if __name__ == "__main__":
    main()