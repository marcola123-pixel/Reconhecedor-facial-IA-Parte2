from test_api import api_module
import sqlite3
from contextlib import closing

import pytest


def test_delete_history_unicode(api_module, tmp_path, monkeypatch):
    main = api_module
    banco = tmp_path / "privacy_history.db"

    monkeypatch.setattr(main, "HISTORY_DB_PATH", banco)

    with closing(sqlite3.connect(banco)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE recognition_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )
            """)

            conn.executemany(
                "INSERT INTO recognition_events (name) VALUES (?)",
                [
                    ("Jos\u00e9",),
                    ("JOS\u00c9",),
                    ("Maria",),
                ]
            )

    deleted = main.delete_history_for_person("Jos\u00e9")

    assert deleted == 2

    with closing(sqlite3.connect(banco)) as conn:
        restantes = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM recognition_events"
            )
        ]

    assert restantes == ["Maria"]


def test_delete_history_without_matches(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    banco = tmp_path / "empty_history.db"

    monkeypatch.setattr(main, "HISTORY_DB_PATH", banco)

    with closing(sqlite3.connect(banco)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE recognition_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )
            """)

    deleted = main.delete_history_for_person("Inexistente")

    assert deleted == 0


def test_api_delete_removes_history(
    api_module, tmp_path, monkeypatch
):
    import numpy as np
    from test_api import make_request, prepare_api

    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    embeddings = np.array([
        [1.0, 0.0],
        [1.0, 0.0],
        [1.0, 0.0],
    ])

    main.gallery.enroll("Jos\u00e9", embeddings)
    main.gallery.enroll("Maria", embeddings)

    with closing(sqlite3.connect(main.HISTORY_DB_PATH)) as conn:
        with conn:
            conn.executemany(
                """
                INSERT INTO recognition_events
                (created_at, name, authorized, similarity)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("2026-11-19T12:00:00", "Jos\u00e9", 1, 0.9),
                    ("2026-11-19T12:01:00", "JOS\u00c9", 1, 0.9),
                    ("2026-11-19T12:02:00", "Maria", 1, 0.9),
                ],
            )

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Jos%C3%A9",
        headers=headers,
    )

    assert response.status_code == 200
    assert main.gallery.names() == ["Maria"]

    with closing(sqlite3.connect(main.HISTORY_DB_PATH)) as conn:
        remaining = conn.execute(
            "SELECT name FROM recognition_events"
        ).fetchall()

    assert remaining == [("Maria",)]


def test_api_delete_history_failure_reports_error(
    api_module, tmp_path, monkeypatch
):
    import numpy as np
    from test_api import make_request, prepare_api

    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Falha",
        np.array([
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ]),
    )

    def fail_history(name):
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(
        main, "delete_history_for_person", fail_history
    )

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa%20Falha",
        headers=headers,
    )

    assert response.status_code == 500

    events = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert any(
        event["tipo"] == "person_deleted"
        and event["sucesso"] is False
        for event in events
    )


def test_api_delete_gallery_save_failure_restores_memory(
    api_module, tmp_path, monkeypatch
):
    import numpy as np
    from pathlib import Path
    from test_api import make_request, prepare_api
    from facerec.gallery import Gallery

    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa NPZ",
        np.array([[1.0, 0.0]] * 3),
    )
    main.gallery.save(main.GALLERY_PATH)

    original_save = main.gallery.save

    def fail_save(path):
        raise OSError("simulated NPZ failure")

    monkeypatch.setattr(main.gallery, "save", fail_save)

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa%20NPZ",
        headers=headers,
    )

    assert response.status_code == 500
    assert main.gallery.names() == ["Pessoa NPZ"]

    persisted = Gallery.load(
        main.GALLERY_PATH,
        expected_model_id="modelo_teste",
    )
    assert persisted.names() == ["Pessoa NPZ"]


def test_api_delete_history_failure_restores_gallery(
    api_module, tmp_path, monkeypatch
):
    import sqlite3
    import numpy as np
    from contextlib import closing
    from test_api import make_request, prepare_api
    from facerec.gallery import Gallery

    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa SQLite",
        np.array([[1.0, 0.0]] * 3),
    )
    main.gallery.save(main.GALLERY_PATH)

    with closing(sqlite3.connect(main.HISTORY_DB_PATH)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO recognition_events
                (created_at, name, authorized, similarity)
                VALUES (?, ?, ?, ?)
                """,
                ("2026-11-19T12:00:00", "Pessoa SQLite", 1, 0.9),
            )

    def fail_history(name):
        raise sqlite3.OperationalError("simulated SQLite failure")

    monkeypatch.setattr(
        main, "delete_history_for_person", fail_history
    )

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa%20SQLite",
        headers=headers,
    )

    assert response.status_code == 500
    assert main.gallery.names() == ["Pessoa SQLite"]

    persisted = Gallery.load(
        main.GALLERY_PATH,
        expected_model_id="modelo_teste",
    )
    assert persisted.names() == ["Pessoa SQLite"]

    with closing(sqlite3.connect(main.HISTORY_DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT name FROM recognition_events"
        ).fetchall()

    assert rows == [("Pessoa SQLite",)]
