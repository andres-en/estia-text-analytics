from __future__ import annotations

from sqlalchemy import inspect

from clasificador.db.engine import apply_ddl_file, create_db_engine


def test_apply_ddl_file_ignora_punto_y_coma_dentro_de_un_comentario(tmp_path):
    """Un comentario con un ';' en medio (ej. una nota de negocio en español)
    no debe cortar la sentencia CREATE TABLE a la mitad — bug real que rompió
    el aprovisionamiento de un cliente nuevo cuando `sql/ddl.sql` ganó un
    comentario con esa forma."""
    ddl_path = tmp_path / "ddl.sql"
    ddl_path.write_text(
        """
        CREATE TABLE ejemplo (
            id INTEGER PRIMARY KEY,
            -- Nota con punto y coma; sigue siendo un comentario, no un separador.
            nombre TEXT NOT NULL
        );
        """,
        encoding="utf-8",
    )
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    apply_ddl_file(engine, ddl_path)

    columnas = {c["name"] for c in inspect(engine).get_columns("ejemplo")}
    assert columnas == {"id", "nombre"}


def test_apply_ddl_file_aplica_varias_sentencias(tmp_path):
    ddl_path = tmp_path / "ddl.sql"
    ddl_path.write_text(
        """
        CREATE TABLE a (id INTEGER PRIMARY KEY);
        CREATE TABLE b (id INTEGER PRIMARY KEY);
        """,
        encoding="utf-8",
    )
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    apply_ddl_file(engine, ddl_path)

    assert set(inspect(engine).get_table_names()) == {"a", "b"}
