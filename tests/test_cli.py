import json

from la_caja.cli import main


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_cli_observe_query_stats_roundtrip(tmp_path, capsys):
    db = str(tmp_path / "memoria.db")

    assert main(["observe", "--db", db, "gravedad", "masa"]) == 0
    observed = _json(capsys)
    assert "gravedad" in observed["terminos_procesados"]

    assert main(["query", "--db", db, "gravedad", "masa"]) == 0
    relation = _json(capsys)
    assert relation["confidence"] == 1.0
    assert relation["kind"] == "observed"

    assert main(["stats", "--db", db]) == 0
    stats = _json(capsys)
    assert stats["terminos"] == 2


def test_cli_ingest_uses_batch_and_reports_count(tmp_path, capsys):
    db = str(tmp_path / "memoria.db")
    source = tmp_path / "observaciones.txt"
    source.write_text("gravedad masa energia\nsol luna\n\n", encoding="utf-8")

    assert main(["ingest", "--db", db, str(source)]) == 0
    result = _json(capsys)
    assert result["observaciones"] == 2
    assert result["stats"]["terminos"] >= 4


def test_cli_prime_returns_bounded_context(tmp_path, capsys):
    db = str(tmp_path / "memoria.db")
    main(["observe", "--db", db, "gravedad masa energia"])
    capsys.readouterr()

    assert main(["prime", "--db", db, "--budget", "2", "gravedad"]) == 0
    result = _json(capsys)
    assert len(result["context"]) <= 2
