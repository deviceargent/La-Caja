"""Interfaz de linea de comandos para La Caja."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from . import LaCaja


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="la-caja",
        description="Memoria contextual asociativa local con persistencia SQLite.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    observe = sub.add_parser("observe", help="Incorpora una observacion textual.")
    observe.add_argument("--db", required=True, help="Archivo SQLite de la memoria.")
    observe.add_argument("--rehidratar", action="store_true")
    observe.add_argument("text", nargs="+", help="Texto observado.")

    ingest = sub.add_parser("ingest", help="Incorpora un archivo de texto, una linea por observacion.")
    ingest.add_argument("--db", required=True, help="Archivo SQLite de la memoria.")
    ingest.add_argument("--rehidratar", action="store_true")
    ingest.add_argument("file", help="Archivo UTF-8 o '-' para stdin.")

    relation = sub.add_parser("relate", help="Registra la co-ocurrencia de dos conceptos.")
    relation.add_argument("--db", required=True)
    relation.add_argument("term_a")
    relation.add_argument("term_b")

    query = sub.add_parser("query", help="Consulta la confianza entre dos conceptos.")
    query.add_argument("--db", required=True)
    query.add_argument("term_a")
    query.add_argument("term_b")

    prime = sub.add_parser("prime", help="Recupera contexto asociado a un concepto.")
    prime.add_argument("--db", required=True)
    prime.add_argument("--budget", type=int, default=5)
    prime.add_argument("term")

    stats = sub.add_parser("stats", help="Muestra el tamano de la memoria.")
    stats.add_argument("--db", required=True)

    history = sub.add_parser("history", help="Consulta trazas dormidas de un concepto.")
    history.add_argument("--db", required=True)
    history.add_argument("term")

    optimize = sub.add_parser("optimize", help="Ejecuta olvido y consolidacion.")
    optimize.add_argument("--db", required=True)

    cartography = sub.add_parser("cartography", help="Mide y exporta la estructura del grafo.")
    cartography.add_argument("--db", required=True)
    cartography.add_argument("--html", type=Path)
    cartography.add_argument("--gexf", type=Path)

    return parser


def _emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "cartography" and not (args.html or args.gexf):
        parser.error("cartography requiere al menos --html o --gexf")

    try:
        with LaCaja(db_path=args.db, rehidratar=getattr(args, "rehidratar", False)) as caja:
            if args.command == "observe":
                _emit(caja.procesar_consulta(" ".join(args.text)))
            elif args.command == "ingest":
                def ingest_lines(source):
                    count = 0
                    with caja.lote():
                        for line in source:
                            text = line.strip()
                            if text:
                                caja.procesar_consulta(text)
                                count += 1
                    return count

                if args.file == "-":
                    total = ingest_lines(sys.stdin)
                else:
                    with Path(args.file).open("r", encoding="utf-8") as source:
                        total = ingest_lines(source)
                _emit({"observaciones": total, "stats": caja.stats()})
            elif args.command == "relate":
                _emit(caja.declarar_relacion(args.term_a, args.term_b))
            elif args.command == "query":
                confidence = caja.consultar(args.term_a, args.term_b)
                kind = "observed" if confidence == 1.0 else "inferred" if confidence > 0 else "none"
                _emit({"a": args.term_a, "b": args.term_b, "confidence": confidence, "kind": kind})
            elif args.command == "prime":
                if args.budget < 0:
                    parser.error("--budget debe ser >= 0")
                _emit({"term": args.term, "context": caja.contexto_primado(args.term, args.budget)})
            elif args.command == "stats":
                _emit(caja.stats())
            elif args.command == "history":
                _emit(caja.historial(args.term))
            elif args.command == "optimize":
                _emit({"optimization": caja.optimizar(), "stats": caja.stats()})
            elif args.command == "cartography":
                from .cartografia import descubrir, medir
                from .cartografia.visualizar import exportar_gexf, exportar_html

                medidas, estructuras = medir(caja.piscina)
                candidatos, resumen = descubrir(caja.piscina)
                if args.html:
                    exportar_html(caja.piscina, str(args.html), candidatos=candidatos)
                if args.gexf:
                    exportar_gexf(caja.piscina, str(args.gexf))
                _emit({
                    "measurements": medidas,
                    "structures": estructuras,
                    "candidate_summary": resumen,
                    "candidates": len(candidatos),
                    "html": str(args.html) if args.html else None,
                    "gexf": str(args.gexf) if args.gexf else None,
                })
        return 0
    except (OSError, RuntimeError, ValueError, ImportError, sqlite3.Error) as exc:
        print(f"la-caja: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
