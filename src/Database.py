"""Couche d'archivage SQLite des injections.

Chaque injection réussie est enregistrée ici : c'est la mémoire durable du projet,
qui alimente la page « Historique » du web et permet la détection de doublons
(un même texte enrichi ne doit pas être réinjecté par erreur).

Choix techniques :
  - `sqlite3` de la stdlib, une connexion ouverte par opération (via context
    manager). Pour un usage local mono-utilisateur, c'est suffisant et cela évite
    les soucis de partage de connexion entre threads (FastAPI).
  - anti-doublon par empreinte SHA-256 du texte injecté normalisé (voir
    `compute_text_hash`), stockée et indexée.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime


def compute_text_hash(text):
    """Empreinte stable du texte injecté, pour la détection de doublon.

    Normalise les espaces de bord et la casse n'est PAS touchée (un texte identique
    au caractère près = doublon ; une reformulation = entrée légitime distincte).
    """
    normalized = (text or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Colonnes exposées telles quelles vers l'UI / l'appelant.
_COLUMNS = [
    "id", "date_injection", "categorie", "arc", "entry_number",
    "date_session", "resume", "texte", "metadata_json", "xml_file",
    "pdf_path", "hash_texte",
]


class InjectionDatabase:
    def __init__(self, db_path=None):
        # Défaut : data/injections.db à la racine du projet (local, hors partage
        # réseau où vivent les JSON/XML). Configurable via l'appelant ou DATABASE_PATH.
        if db_path is None:
            db_path = os.getenv("DATABASE_PATH") or os.path.join("data", "injections.db")
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS injections (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_injection TEXT NOT NULL,
                    categorie      TEXT,
                    arc            TEXT,
                    entry_number   INTEGER,
                    date_session   TEXT,
                    resume         TEXT,
                    texte          TEXT,
                    metadata_json  TEXT,
                    xml_file       TEXT,
                    pdf_path       TEXT,
                    hash_texte     TEXT
                )
                """
            )
            # Index anti-doublon + accélère les filtres de l'historique.
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON injections(hash_texte)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_categorie ON injections(categorie)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_arc ON injections(arc)")

    # --- Anti-doublon --------------------------------------------------------

    def find_duplicate(self, text_hash):
        """Retourne l'injection existante ayant ce hash, ou None.

        Utilisé AVANT injection : si non-None, le texte a déjà été traité.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM injections WHERE hash_texte = ? ORDER BY id DESC LIMIT 1",
                (text_hash,),
            ).fetchone()
        return dict(row) if row else None

    # --- Écriture ------------------------------------------------------------

    def record_injection(self, *, categorie, arc, entry_number, date_session,
                         resume, texte, metadata=None, xml_file=None,
                         pdf_path=None, text_hash=None):
        """Enregistre une injection réussie. Retourne l'id de la ligne créée."""
        if text_hash is None:
            text_hash = compute_text_hash(texte)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO injections
                    (date_injection, categorie, arc, entry_number, date_session,
                     resume, texte, metadata_json, xml_file, pdf_path, hash_texte)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    categorie, arc, entry_number, date_session,
                    resume, texte, metadata_json, xml_file, pdf_path, text_hash,
                ),
            )
            return cur.lastrowid

    # --- Lecture (historique web) --------------------------------------------

    def list_injections(self, categorie=None, arc=None, search=None,
                        limit=50, offset=0):
        """Historique filtrable (catégorie, arc, recherche plein-texte simple)."""
        clauses, params = [], []
        if categorie:
            clauses.append("categorie = ?")
            params.append(categorie)
        if arc:
            clauses.append("arc = ?")
            params.append(arc)
        if search:
            clauses.append("(texte LIKE ? OR resume LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = (
            f"SELECT * FROM injections {where} "
            f"ORDER BY id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def count(self, categorie=None, arc=None, search=None):
        """Nombre total d'injections correspondant aux filtres (pagination)."""
        clauses, params = [], []
        if categorie:
            clauses.append("categorie = ?")
            params.append(categorie)
        if arc:
            clauses.append("arc = ?")
            params.append(arc)
        if search:
            clauses.append("(texte LIKE ? OR resume LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM injections {where}", params).fetchone()
        return row["n"]

    def get_injection(self, injection_id):
        """Détail d'une injection par id (page détail / regénération PDF)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM injections WHERE id = ?", (injection_id,)
            ).fetchone()
        return dict(row) if row else None

    def distinct_arcs(self):
        """Arcs déjà rencontrés en base (pour peupler un filtre de l'historique)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT arc FROM injections WHERE arc IS NOT NULL ORDER BY arc"
            ).fetchall()
        return [r["arc"] for r in rows]
