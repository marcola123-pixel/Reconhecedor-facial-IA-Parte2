"""Auditoria persistente de eventos administrativos."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 30

ALLOWED_EVENTS = {
    "admin_login_success",
    "admin_login_failure",
    "admin_access_denied",
    "person_created",
    "person_deleted",
    "admin_logout",
    "session_expired",
    "security_block",
}


def init_audit_db(db_path):
    """Inicializa a base de auditoria sem apagar registros existentes."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                success INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_security_events_created
            ON security_events(created_at)
        """)


def record_security_event(db_path, event_type, success):
    """Registra somente eventos permitidos, sem tokens ou dados biometricos."""
    if event_type not in ALLOWED_EVENTS:
        raise ValueError("Tipo de evento de seguranca invalido.")

    if not isinstance(success, bool):
        raise ValueError("O resultado do evento deve ser booleano.")

    db_path = Path(db_path)

    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")
    cutoff = (now - timedelta(days=RETENTION_DAYS)).isoformat(
        timespec="seconds"
    )

    with sqlite3.connect(db_path, timeout=10) as conn:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute(
            "DELETE FROM security_events WHERE created_at < ?",
            (cutoff,),
        )

        conn.execute(
            """
            INSERT INTO security_events (
                created_at, event_type, success
            ) VALUES (?, ?, ?)
            """,
            (timestamp, event_type, int(success)),
        )

    return True


def read_security_events(db_path, limit=100):
    """Consulta eventos recentes com limite maximo de 200 registros."""
    limit = max(1, min(int(limit), 200))
    db_path = Path(db_path)

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    ).isoformat(timespec="seconds")

    with sqlite3.connect(db_path, timeout=10) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT id, created_at, event_type, success
            FROM security_events
            WHERE created_at >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "data_hora": row["created_at"],
            "tipo": row["event_type"],
            "sucesso": bool(row["success"]),
        }
        for row in rows
    ]
