"""Persistance de la carte des touches (SQLite).

Même forme que `InjectionDatabase` : `sqlite3` de la stdlib, une connexion ouverte
par opération, schéma auto-créé. Base **séparée** (`data/keybinds.db`) : le mémo
clavier n'a rien à voir avec l'archivage narratif des injections.

Le scan code est la **clé primaire** de la table. La règle « une touche = une
action » est donc portée par le schéma et non par une convention d'usage : un
conflit d'assignation est impossible par construction, l'écriture d'un bind
existant l'écrase (UPSERT).
"""

import os
import sqlite3
from datetime import datetime

from src.KeyboardLayout import DEFAULT_BINDS

_COLUMNS = ["scan_code", "action", "cat", "note", "updated_at"]


class KeyBindDatabase:
    def __init__(self, db_path=None):
        # Défaut : data/keybinds.db à la racine du projet, comme injections.db.
        if db_path is None:
            db_path = os.getenv("KEYBINDS_DB_PATH") or os.path.join("data", "keybinds.db")
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        self._init_schema()
        self._seed_if_empty()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keybinds (
                    scan_code  INTEGER PRIMARY KEY,
                    action     TEXT NOT NULL,
                    cat        TEXT NOT NULL,
                    note       TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_keybind_cat ON keybinds(cat)")

    def _seed_if_empty(self):
        """Amorce la base avec le mapping de départ, au tout premier lancement.

        Uniquement si la table est vide : une carte vidée volontairement le reste,
        on ne réinjecte jamais le semis par-dessus les choix de l'utilisateur.
        """
        with self._connect() as conn:
            if conn.execute("SELECT COUNT(*) AS n FROM keybinds").fetchone()["n"]:
                return
            now = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                "INSERT INTO keybinds (scan_code, action, cat, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (code, action, cat, note, now)
                    for code, (action, cat, note) in DEFAULT_BINDS.items()
                ],
            )

    # --- Lecture -------------------------------------------------------------

    def all_binds(self):
        """Retourne {scan_code: {action, cat, note, updated_at}}.

        Indexé par scan code : les gabarits font un simple `binds.get(code)` par
        touche, sans parcourir de liste.
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM keybinds").fetchall()
        return {r["scan_code"]: dict(r) for r in rows}

    def get_bind(self, scan_code):
        """Détail d'un bind, ou None si la touche est libre."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM keybinds WHERE scan_code = ?", (scan_code,)
            ).fetchone()
        return dict(row) if row else None

    def count_by_category(self):
        """{famille: nombre de touches assignées}, pour les compteurs du bandeau."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT cat, COUNT(*) AS n FROM keybinds GROUP BY cat"
            ).fetchall()
        return {r["cat"]: r["n"] for r in rows}

    # --- Écriture ------------------------------------------------------------

    def set_bind(self, scan_code, action, cat, note=""):
        """Assigne (ou réassigne) une touche. Écrase le bind existant."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO keybinds (scan_code, action, cat, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scan_code) DO UPDATE SET
                    action = excluded.action,
                    cat = excluded.cat,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    scan_code, action.strip(), cat, (note or "").strip(),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def clear_bind(self, scan_code):
        """Libère une touche (retour à l'état éteint)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM keybinds WHERE scan_code = ?", (scan_code,))

    # --- Export --------------------------------------------------------------

    def export_payload(self):
        """Structure sérialisable en JSON, triée par scan code (diff lisible)."""
        binds = self.all_binds()
        return {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(binds),
            "binds": [
                {
                    "scan_code": code,
                    "action": b["action"],
                    "cat": b["cat"],
                    "note": b["note"] or "",
                }
                for code, b in sorted(binds.items())
            ],
        }
