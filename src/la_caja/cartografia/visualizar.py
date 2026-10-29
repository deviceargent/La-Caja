"""Etapa C (render) -- visualizacion interactiva SOLO LECTURA.

Genera un HTML autocontenido (sin dependencias de red) con el grafo de
conceptos: layout precomputado en Python (networkx spring_layout con
semilla fija, reproducible), navegacion pan/zoom/seleccion en canvas con
JavaScript embebido, panel de evidencia y capas filtrables (observada /
activacion).

Advertencia de distancia (ver docs/cartografia.md): la posicion 2D es un
producto del layout; NO es distancia semantica ni distancia de grafo. El
HTML lo declara explicitamente.

Tambien exporta GEXF para herramientas externas (Gephi) cuando se
quiere inspeccion fuera del navegador. La exportacion nunca muta la
piscina.
"""
from __future__ import annotations

import json

import networkx as nx

from .medir import grafo_conceptos, grafo_observado, _comunidades


PALETA = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e",
]


def exportar_html(piscina, ruta, titulo="La Caja -- cartografia", candidatos=None):
    """Escribe un HTML autocontenido con el estado vivo del grafo de
    conceptos. `candidatos` (opcional, de descubrir()) se incrusta para
    que el panel muestre POR QUE un nodo fue marcado interesante.
    SOLO LECTURA sobre la piscina."""
    g_con = grafo_conceptos(piscina)
    obs = grafo_observado(g_con)
    particion, _ = _comunidades(g_con)

    # Layout determinista sobre la capa observada; los nodos sin aristas
    # observadas quedan en el borde para no pisar la estructura real.
    base = obs.subgraph([n for n in obs.nodes()])
    pos = {}
    if base.number_of_nodes():
        pos = nx.spring_layout(base, seed=0, k=1.8 / max(1, base.number_of_nodes()) ** 0.5)
    aislados = [n for n in g_con.nodes() if n not in pos]
    for i, n in enumerate(sorted(aislados)):
        import math
        ang = 2 * math.pi * i / max(1, len(aislados))
        pos[n] = (1.35 * math.cos(ang), 1.35 * math.sin(ang))

    nodos = []
    for n, d in g_con.nodes(data=True):
        nodos.append({
            "id": n,
            "x": round(float(pos[n][0]), 4),
            "y": round(float(pos[n][1]), 4),
            "peso": d.get("peso", 1),
            "nivel": d.get("nivel", 0),
            "membresias": d.get("membresias", 0),
            "comunidad": particion.get(n, -1),
        })
    aristas = []
    for u, v, d in g_con.edges(data=True):
        aristas.append({
            "s": u,
            "t": v,
            "tipo": d.get("tipo", "observada"),
            "peso": d.get("peso", 1),
            "refuerzos": d.get("refuerzos"),
        })

    datos = {
        "titulo": titulo,
        "nodos": nodos,
        "aristas": aristas,
        "candidatos": candidatos or [],
        "advertencia": (
            "Las posiciones son el resultado de un layout determinista "
            "(spring_layout, semilla 0) sobre la capa observada. La distancia "
            "visual NO es distancia semantica ni distancia de grafo: es solo "
            "una representacion 2D navegable."
        ),
    }
    json_datos = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")

    html = _PLANTILLA_HTML.replace("__DATOS__", json_datos).replace("__TITULO__", titulo)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    return ruta


def exportar_gexf(piscina, ruta):
    """Exporta el grafo de conceptos a GEXF (formato estandar de Gephi).
    La arista lleva su tipo (observada/activacion) como atributo: la
    capa nunca se colapsa. SOLO LECTURA."""
    g = grafo_conceptos(piscina)
    for _, _, d in g.edges(data=True):
        d["peso"] = float(d.get("peso", 1))
    for _, d in g.nodes(data=True):
        d["peso"] = float(d.get("peso", 1))
    nx.write_gexf(g, ruta)
    return ruta


_PLANTILLA_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>__TITULO__</title>
<style>
  html, body { margin:0; height:100%; background:#0f1117; color:#d7dae0;
               font-family:Consolas, "Segoe UI", monospace; overflow:hidden; }
  #lienzo { position:absolute; inset:0; cursor:grab; }
  #panel { position:absolute; top:0; right:0; width:360px; height:100%;
           background:#171a23; border-left:1px solid #2b3040; padding:14px;
           overflow-y:auto; box-sizing:border-box; font-size:13px; }
  #panel h2 { font-size:15px; margin:0 0 6px; color:#fff; }
  #panel .adv { color:#8b91a0; font-size:11px; line-height:1.4; margin-bottom:10px; }
  #controles label { margin-right:10px; font-size:12px; color:#aab0bd; }
  .cand { background:#1f2431; border:1px solid #333a4d; border-radius:6px;
          padding:8px; margin:8px 0; }
  .cand .tipo { font-size:11px; color:#8ab4f8; text-transform:uppercase; }
  .cand .titulo { margin:3px 0; color:#e8eaed; }
  .cand pre { font-size:11px; color:#9aa2b1; white-space:pre-wrap; margin:4px 0 0; }
  .elem { color:#7fd1a8; cursor:pointer; text-decoration:underline dotted; }
  table { border-collapse:collapse; font-size:12px; margin-top:6px; }
  td { padding:2px 8px 2px 0; color:#aab0bd; }
  td.k { color:#6c7383; }
  #buscador { width:100%; box-sizing:border-box; margin:8px 0; padding:6px;
              background:#0f1117; color:#d7dae0; border:1px solid #2b3040; }
</style>
</head>
<body>
<canvas id="lienzo"></canvas>
<div id="panel">
  <h2 id="titulo">__TITULO__</h2>
  <div class="adv" id="advertencia"></div>
  <div id="controles">
    <label><input type="checkbox" id="capa_obs" checked> observadas</label>
    <label><input type="checkbox" id="capa_act"> activacion</label>
    <label><input type="checkbox" id="capa_etiq" checked> etiquetas</label>
  </div>
  <input id="buscador" placeholder="buscar termino...">
  <div id="detalle">Selecciona un nodo para inspeccionar su evidencia.</div>
  <h2>Candidatos (<span id="ncand">0</span>)</h2>
  <div id="candidatos"></div>
</div>
<script>
const DATOS = __DATOS__;
const canvas = document.getElementById("lienzo");
const ctx = canvas.getContext("2d");
let vista = { x: 0, y: 0, escala: 1 };
let seleccion = null;
const nodosPorId = {};
DATOS.nodos.forEach(n => nodosPorId[n.id] = n);
const vecinosDe = {};
DATOS.aristas.forEach(a => {
  (vecinosDe[a.s] = vecinosDe[a.s] || []).push({ otro: a.t, arista: a });
  (vecinosDe[a.t] = vecinosDe[a.t] || []).push({ otro: a.s, arista: a });
});
const PALETA = ["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948",
  "#b07aa1","#ff9da7","#9c755f","#bab0ac","#1b9e77","#d95f02","#7570b3",
  "#e7298a","#66a61e"];

document.getElementById("advertencia").textContent = DATOS.advertencia;

function redim() {
  canvas.width = innerWidth * devicePixelRatio;
  canvas.height = innerHeight * devicePixelRatio;
  canvas.style.width = innerWidth + "px";
  canvas.style.height = innerHeight + "px";
}
addEventListener("resize", redim);
redim();
vista.escala = Math.min(innerWidth - 360, innerHeight) / 3.2;
vista.x = (innerWidth - 360) / 2;
vista.y = innerHeight / 2;

function aPantalla(p) {
  return { x: vista.x + p.x * vista.escala, y: vista.y + p.y * vista.escala };
}
function radio(n) { return 3 + Math.sqrt(n.peso) * 1.6; }

function dibujar() {
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const verObs = document.getElementById("capa_obs").checked;
  const verAct = document.getElementById("capa_act").checked;
  const verEtiq = document.getElementById("capa_etiq").checked;
  // aristas
  for (const a of DATOS.aristas) {
    if (a.tipo === "observada" && !verObs) continue;
    if (a.tipo === "activacion" && !verAct) continue;
    const p1 = aPantalla(nodosPorId[a.s]), p2 = aPantalla(nodosPorId[a.t]);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    if (a.tipo === "activacion") { ctx.strokeStyle = "rgba(150,150,170,0.18)"; ctx.setLineDash([3,4]); }
    else { ctx.strokeStyle = "rgba(130,170,255,0.35)"; ctx.setLineDash([]); }
    ctx.lineWidth = Math.min(4, 0.6 + Math.log2(1 + (a.peso || 1)) * 0.7);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  // nodos
  for (const n of DATOS.nodos) {
    const p = aPantalla(n);
    ctx.beginPath();
    ctx.arc(p.x, p.y, radio(n), 0, 6.2832);
    const c = PALETA[((n.comunidad % PALETA.length) + PALETA.length) % PALETA.length];
    ctx.fillStyle = n === seleccion ? "#ffffff" : c;
    ctx.fill();
    if (n === seleccion) { ctx.strokeStyle = c; ctx.lineWidth = 2.5; ctx.stroke(); }
    if (verEtiq && (vista.escala > 90 || n === seleccion)) {
      ctx.fillStyle = "#c9cedb";
      ctx.font = "11px Consolas, monospace";
      ctx.fillText(n.id, p.x + radio(n) + 3, p.y + 3);
    }
  }
}

function nodoEn(px, py) {
  for (let i = DATOS.nodos.length - 1; i >= 0; i--) {
    const n = DATOS.nodos[i], p = aPantalla(n);
    const r = radio(n) + 3;
    if ((px - p.x) ** 2 + (py - p.y) ** 2 <= r * r) return n;
  }
  return null;
}

function mostrarDetalle(n) {
  const d = document.getElementById("detalle");
  if (!n) { d.textContent = "Selecciona un nodo para inspeccionar su evidencia."; return; }
  const cand = DATOS.candidatos.filter(c =>
    (c.elementos && c.elementos.terminos || []).includes(n.id));
  let html = "<h2>" + n.id + "</h2><table>" +
    "<tr><td class='k'>peso</td><td>" + n.peso + "</td></tr>" +
    "<tr><td class='k'>nivel</td><td>" + n.nivel + "</td></tr>" +
    "<tr><td class='k'>membresias</td><td>" + n.membresias + "</td></tr>" +
    "<tr><td class='k'>comunidad</td><td>" + n.comunidad + "</td></tr></table>";
  const vec = vecinosDe[n.id] || [];
  if (vec.length) {
    html += "<p>Vecinos (" + vec.length + "):</p>";
    for (const v of vec.slice(0, 40)) {
      html += "<span class='elem' data-id='" + v.otro + "'>" + v.otro + "</span> <small>(" +
        v.arista.tipo + ", f=" + v.arista.peso + ")</small><br>";
    }
  }
  if (cand.length) {
    html += "<h2>Por que es interesante</h2>";
    for (const c of cand) {
      html += "<div class='cand'><div class='tipo'>" + c.tipo + "</div>" +
        "<div class='titulo'>" + c.titulo + "</div><pre>" +
        JSON.stringify(c.evidencia, null, 1) + "</pre></div>";
    }
  }
  d.innerHTML = html;
  d.querySelectorAll(".elem").forEach(e => e.onclick = () => {
    seleccion = nodosPorId[e.dataset.id]; mostrarDetalle(seleccion); dibujar();
  });
}

function renderCandidatos() {
  const cont = document.getElementById("candidatos");
  document.getElementById("ncand").textContent = DATOS.candidatos.length;
  let html = "";
  for (const c of DATOS.candidatos) {
    html += "<div class='cand'><div class='tipo'>" + c.tipo + "</div>" +
      "<div class='titulo'>";
    const ts = (c.elementos && c.elementos.terminos) || [];
    if (ts.length && ts.length <= 4) {
      for (const t of ts) html += "<span class='elem' data-id='" + t + "'>" + t + "</span> ";
      html += "<br>" + c.titulo;
    } else html += c.titulo;
    html += "</div><pre>" + JSON.stringify(c.evidencia, null, 1) + "</pre></div>";
  }
  cont.innerHTML = html || "<i>sin candidatos</i>";
  cont.querySelectorAll(".elem").forEach(e => e.onclick = () => {
    seleccion = nodosPorId[e.dataset.id]; mostrarDetalle(seleccion); dibujar();
  });
}
renderCandidatos();

canvas.addEventListener("wheel", ev => {
  ev.preventDefault();
  const f = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  vista.x = ev.clientX - (ev.clientX - vista.x) * f;
  vista.y = ev.clientY - (ev.clientY - vista.y) * f;
  vista.escala *= f;
  dibujar();
}, { passive: false });

let arrastre = null;
canvas.addEventListener("mousedown", ev => { arrastre = { x: ev.clientX, y: ev.clientY, movio: false }; });
addEventListener("mousemove", ev => {
  if (!arrastre) return;
  const dx = ev.clientX - arrastre.x, dy = ev.clientY - arrastre.y;
  if (Math.abs(dx) + Math.abs(dy) > 2) arrastre.movio = true;
  vista.x += dx; vista.y += dy;
  arrastre.x = ev.clientX; arrastre.y = ev.clientY;
  dibujar();
});
addEventListener("mouseup", ev => {
  if (arrastre && !arrastre.movio) {
    seleccion = nodoEn(ev.clientX, ev.clientY);
    mostrarDetalle(seleccion);
    dibujar();
  }
  arrastre = null;
});

document.getElementById("buscador").addEventListener("input", ev => {
  const q = ev.target.value.trim().toLowerCase();
  if (!q) return;
  const n = DATOS.nodos.find(x => x.id.includes(q));
  if (n) { seleccion = n; mostrarDetalle(n); dibujar(); }
});
document.getElementById("capa_obs").onchange = dibujar;
document.getElementById("capa_act").onchange = dibujar;
document.getElementById("capa_etiq").onchange = dibujar;
dibujar();
</script>
</body>
</html>
"""