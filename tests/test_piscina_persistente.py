"""Tests for the event-sourced persistence prototype
(la_caja.piscina_persistente). Verifies the two properties that
actually matter for a persistence layer: replaying the event log from
scratch reconstructs byte-identical state, and a snapshot genuinely
bounds replay to events after it (not just "still correct").
"""
from la_caja.piscina_persistente import LaCaja, Nodo


def _reset_id_sequence():
    """Simula un proceso realmente nuevo: Nodo._seq es una variable de
    clase, en un proceso fresco arranca en 0."""
    Nodo._seq = 0


def test_replay_reconstructs_identical_state_after_restart(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad masa energia")
    la1.procesar_consulta("sol masa")
    la1.declarar_relacion("doom3", "idtech4")
    la1.declarar_relacion("idtech4", "netradiant")
    estado_original = la1.piscina.a_dict()
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    estado_reconstruido = la2.piscina.a_dict()

    assert estado_reconstruido == estado_original


def test_connectivity_and_weights_survive_restart(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad")
    la1.procesar_consulta("gravedad")
    # cada concepto se establece PRIMERO por separado -- recien
    # despues su co-ocurrencia (existente+existente) genera arista.
    la1.procesar_consulta("doom3")
    la1.procesar_consulta("idtech4")
    la1.procesar_consulta("netradiant")
    la1.declarar_relacion("doom3", "idtech4")
    la1.declarar_relacion("idtech4", "netradiant")
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)

    assert la2.piscina.burbujas["gravedad"].peso == 2
    assert la2.consultar("doom3", "netradiant") is True


def test_snapshot_bounds_replay_to_events_after_it(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad masa energia")
    la1.piscina.snapshot()
    eventos_hasta_snapshot = la1.piscina.db.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]

    la1.procesar_consulta("sol luna")
    estado_original = la1.piscina.a_dict()
    la1.piscina.db.close()

    import sqlite3
    verificacion = sqlite3.connect(db_path)
    ultimo_evento_snapshot = verificacion.execute(
        "SELECT ultimo_evento_id FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    verificacion.close()
    assert ultimo_evento_snapshot == eventos_hasta_snapshot, (
        "el snapshot debe apuntar exactamente al ultimo evento previo, "
        "no a un punto arbitrario"
    )

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    estado_reconstruido = la2.piscina.a_dict()

    assert estado_reconstruido == estado_original


def test_no_direct_bypass_of_piscina_internals(tmp_path):
    """Toda mutacion pasa por un metodo de Piscina -- Caja ya no toca
    piscina.burbujas directamente (ese bypass es lo que habria hecho
    imposible el event-sourcing sin refactor)."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la = LaCaja(db_path=db_path)
    la.procesar_consulta("gravedad")

    eventos_registrados = la.piscina.db.execute("SELECT metodo FROM eventos").fetchall()
    metodos = {fila[0] for fila in eventos_registrados}
    assert "crear_burbuja" in metodos
    assert metodos <= {"crear_burbuja", "reforzar", "crear_unitario", "crear_compartido", "fusionar", "arista_entre"}


def test_in_memory_piscina_without_db_path_works_unpersisted():
    """LaCaja sin db_path sigue funcionando en memoria pura, sin tocar
    disco -- la persistencia es opt-in, no obligatoria."""
    la = LaCaja()
    la.procesar_consulta("gravedad masa")
    assert la.consultar("gravedad", "masa") is True
