import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import secrets
import hashlib

from .config import DB_PATH, FTS_ENABLED, DEFAULT_ORG_ID

ALLOWED_FACT_STATUSES = {"draft", "proposed", "validated", "published", "rejected"}

SCHEMA_SQL = """
-- orgs
CREATE TABLE IF NOT EXISTS orgs (
  org_id TEXT PRIMARY KEY,
  name   TEXT NOT NULL UNIQUE
);

-- universal facts
CREATE TABLE IF NOT EXISTS facts (
  fact_id TEXT PRIMARY KEY,
  org_id  TEXT NOT NULL,
  meeting_id TEXT,
  transcript_id TEXT,
  fact_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  confidence REAL,
  payload TEXT NOT NULL,
  due_iso TEXT,
  due_at DATETIME,
  idempotency_key TEXT UNIQUE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY (org_id) REFERENCES orgs(org_id) ON DELETE CASCADE
);

-- evidence (multiple per fact)
CREATE TABLE IF NOT EXISTS fact_evidence (
  evidence_id TEXT PRIMARY KEY,
  fact_id TEXT NOT NULL,
  quote TEXT,
    who_said_id TEXT,
  who_said_label TEXT,
  ts_start_ms INTEGER,
    utterance_ids TEXT,
    char_span TEXT,
    card_id TEXT,
  FOREIGN KEY (fact_id) REFERENCES facts(fact_id) ON DELETE CASCADE
);

-- entities linked to orgs
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  external_ids TEXT,
  is_active INTEGER DEFAULT 1,
  FOREIGN KEY (org_id) REFERENCES orgs(org_id) ON DELETE CASCADE
);

-- bridge: facts ↔ entities
CREATE TABLE IF NOT EXISTS fact_entities (
  fact_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  role TEXT,
  PRIMARY KEY (fact_id, entity_id),
  FOREIGN KEY (fact_id) REFERENCES facts(fact_id) ON DELETE CASCADE,
  FOREIGN KEY (entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

-- transcripts registry
CREATE TABLE IF NOT EXISTS transcripts (
  transcript_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  meeting_id TEXT,
  source TEXT,
  created_at DATETIME NOT NULL,
  FOREIGN KEY (org_id) REFERENCES orgs(org_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_facts_org_created ON facts(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_org_type_created ON facts(org_id, fact_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_org_due ON facts(org_id, due_at);
CREATE INDEX IF NOT EXISTS idx_evidence_fact ON fact_evidence(fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_entities_fact ON fact_entities(fact_id);

CREATE VIRTUAL TABLE IF NOT EXISTS fact_fts USING fts5(
  fact_id UNINDEXED,
  content
);

CREATE VIEW IF NOT EXISTS agenda_proposals AS
SELECT
  f.fact_id,
  f.org_id,
  f.meeting_id,
  f.transcript_id,
  f.status,
  f.confidence,
  f.payload,
  f.created_at,
  f.updated_at
FROM facts f
WHERE f.fact_type = 'meeting_metadata'
  AND json_extract(f.payload, '$.kind') = 'agenda_proposal';
  
-- org context (company profile/context for agents)
CREATE TABLE IF NOT EXISTS org_context (
    org_id TEXT PRIMARY KEY,
    language TEXT,
    context_text TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (org_id) REFERENCES orgs(org_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS org_context_fts USING fts5(
    org_id UNINDEXED,
    content
);

-- global user/company context (applies across orgs)
CREATE TABLE IF NOT EXISTS global_context (
    context_id TEXT PRIMARY KEY,
    language TEXT,
    context_text TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS global_context_fts USING fts5(
    context_id UNINDEXED,
    content
);
"""


@contextmanager
def tx(readonly: bool = False):
    conn = get_conn(readonly=readonly)
    try:
        yield conn
        if readonly:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()


def get_conn(readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_schema(conn)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    for row in cur.fetchall():
        if row[1] == column:
            return True
    return False


def _migrate_schema(conn: sqlite3.Connection) -> None:
    # Ensure new evidence columns exist for compatibility with updated parsing-agent bundle
    if not _column_exists(conn, "fact_evidence", "utterance_ids"):
        conn.execute("ALTER TABLE fact_evidence ADD COLUMN utterance_ids TEXT")
    if not _column_exists(conn, "fact_evidence", "card_id"):
        conn.execute("ALTER TABLE fact_evidence ADD COLUMN card_id TEXT")
    if not _column_exists(conn, "fact_evidence", "char_span"):
        conn.execute("ALTER TABLE fact_evidence ADD COLUMN char_span TEXT")
    if not _column_exists(conn, "fact_evidence", "who_said_id"):
        conn.execute("ALTER TABLE fact_evidence ADD COLUMN who_said_id TEXT")
    # Ensure org_context exists if added post-initialization
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_context (
            org_id TEXT PRIMARY KEY,
            language TEXT,
            context_text TEXT NOT NULL,
            metadata TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (org_id) REFERENCES orgs(org_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS org_context_fts USING fts5(
            org_id UNINDEXED,
            content
        )
        """
    )
    # Ensure global_context tables
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS global_context (
            context_id TEXT PRIMARY KEY,
            language TEXT,
            context_text TEXT NOT NULL,
            metadata TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS global_context_fts USING fts5(
            context_id UNINDEXED,
            content
        )
        """
    )


def ensure_org(org_id: str, name: Optional[str] = None) -> None:
    if not org_id:
        org_id = DEFAULT_ORG_ID
    with tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO orgs(org_id, name) VALUES(?, ?)",
            (org_id, name or org_id),
        )
        if name:
            conn.execute(
                "UPDATE orgs SET name=? WHERE org_id=?",
                (name, org_id),
            )


def list_orgs() -> List[sqlite3.Row]:
    with tx(readonly=True) as conn:
        cur = conn.execute("SELECT org_id, name FROM orgs ORDER BY name ASC")
        return cur.fetchall()


def get_org(org_id: str) -> Optional[sqlite3.Row]:
    with tx(readonly=True) as conn:
        cur = conn.execute("SELECT org_id, name FROM orgs WHERE org_id=?", (org_id,))
        return cur.fetchone()


def find_org_by_text(text: str) -> Optional[sqlite3.Row]:
    needle = (text or "").strip()
    if not needle:
        return None
    with tx(readonly=True) as conn:
        cur = conn.execute(
            "SELECT org_id, name FROM orgs WHERE org_id=? OR LOWER(name)=LOWER(?)",
            (needle, needle),
        )
        row = cur.fetchone()
        if row:
            return row
        cur = conn.execute(
            "SELECT org_id, name FROM orgs WHERE name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (f"%{needle}%",),
        )
        return cur.fetchone()


def _normalize_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        try:
            json.loads(payload)
            return payload
        except Exception:
            pass
        return json.dumps({"text": payload}, ensure_ascii=False, sort_keys=True)
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)


def _ensure_json(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"text": payload}
    return {}


def _flatten_strings(value: Any, results: Optional[List[str]] = None) -> List[str]:
    if results is None:
        results = []
    if isinstance(value, str):
        if value.strip():
            results.append(value.strip())
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_strings(v, results)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _flatten_strings(v, results)
    return results


def refresh_fact_fts(fact_id: str, conn: Optional[sqlite3.Connection] = None) -> None:
    if not FTS_ENABLED:
        return
    local_conn = conn or get_conn()
    should_close = conn is None
    try:
        row = local_conn.execute("SELECT payload FROM facts WHERE fact_id=?", (fact_id,)).fetchone()
        if not row:
            local_conn.execute("DELETE FROM fact_fts WHERE fact_id=?", (fact_id,))
            return
        payload = _ensure_json(row["payload"])
        pieces = []
        for key in ("title", "name", "text", "subject"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                pieces.append(val.strip())
        pieces.extend(_flatten_strings(payload.get("agenda")))
        evidence_rows = local_conn.execute(
            "SELECT quote FROM fact_evidence WHERE fact_id=?",
            (fact_id,),
        ).fetchall()
        for q in evidence_rows:
            quote = q["quote"]
            if isinstance(quote, str) and quote.strip():
                pieces.append(quote.strip())
        content = "\n".join(pieces).strip()
        local_conn.execute("DELETE FROM fact_fts WHERE fact_id=?", (fact_id,))
        if content:
            local_conn.execute(
                "INSERT INTO fact_fts(fact_id, content) VALUES(?, ?)",
                (fact_id, content),
            )
    finally:
        if should_close:
            local_conn.close()


def refresh_org_context_fts(org_id: str, conn: Optional[sqlite3.Connection] = None) -> None:
    if not FTS_ENABLED:
        return
    local_conn = conn or get_conn()
    should_close = conn is None
    try:
        row = local_conn.execute("SELECT context_text FROM org_context WHERE org_id=?", (org_id,)).fetchone()
        local_conn.execute("DELETE FROM org_context_fts WHERE org_id=?", (org_id,))
        if row and row["context_text"]:
            local_conn.execute(
                "INSERT INTO org_context_fts(org_id, content) VALUES(?, ?)",
                (org_id, row["context_text"]),
            )
    finally:
        if should_close:
            local_conn.close()


def refresh_global_context_fts(context_id: str = "default", conn: Optional[sqlite3.Connection] = None) -> None:
    if not FTS_ENABLED:
        return
    local_conn = conn or get_conn()
    should_close = conn is None
    try:
        row = local_conn.execute("SELECT context_text FROM global_context WHERE context_id=?", (context_id,)).fetchone()
        local_conn.execute("DELETE FROM global_context_fts WHERE context_id=?", (context_id,))
        if row and row["context_text"]:
            local_conn.execute(
                "INSERT INTO global_context_fts(context_id, content) VALUES(?, ?)",
                (context_id, row["context_text"]),
            )
    finally:
        if should_close:
            local_conn.close()


def _compute_idempotency_key(org_id: Optional[str], meeting_id: Optional[str], subject: Optional[str], agenda_obj: Any) -> str:
    h = hashlib.sha256()
    h.update((org_id or "").encode("utf-8"))
    h.update((meeting_id or "").encode("utf-8"))
    h.update((subject or "").encode("utf-8"))
    h.update(json.dumps(agenda_obj or {}, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def insert_or_update_fact(fact: Dict[str, Any]) -> str:
    required = {"org_id", "fact_type", "payload"}
    missing = [k for k in required if k not in fact]
    if missing:
        raise ValueError(f"Missing keys for fact: {missing}")
    ensure_org(fact['org_id'])
    now = now_iso()
    payload_text = _serialize_payload(fact["payload"])
    due_at = _normalize_datetime(fact.get("due_at"))
    status = fact.get("status") or "proposed"
    if status not in ALLOWED_FACT_STATUSES:
        raise ValueError(f"Invalid status '{status}'")
    fact_id = fact.get("fact_id")
    idem = fact.get("idempotency_key")
    with tx() as conn:
        if idem:
            row = conn.execute(
                "SELECT fact_id FROM facts WHERE idempotency_key=?",
                (idem,),
            ).fetchone()
            if row:
                fact_id = row["fact_id"]
                conn.execute(
                    """
                    UPDATE facts
                    SET org_id=?, meeting_id=?, transcript_id=?, fact_type=?, status=?, confidence=?,
                        payload=?, due_iso=?, due_at=?, updated_at=?
                    WHERE fact_id=?
                    """,
                    (
                        fact["org_id"],
                        fact.get("meeting_id"),
                        fact.get("transcript_id"),
                        fact["fact_type"],
                        status,
                        fact.get("confidence"),
                        payload_text,
                        fact.get("due_iso"),
                        due_at,
                        now,
                        fact_id,
                    ),
                )
                refresh_fact_fts(fact_id, conn=conn)
                return fact_id
        if not fact_id:
            fact_id = secrets.token_hex(16)
        conn.execute(
            """
            INSERT INTO facts(
                fact_id, org_id, meeting_id, transcript_id, fact_type, status, confidence,
                payload, due_iso, due_at, idempotency_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                fact["org_id"],
                fact.get("meeting_id"),
                fact.get("transcript_id"),
                fact["fact_type"],
                status,
                fact.get("confidence"),
                payload_text,
                fact.get("due_iso"),
                due_at,
                idem,
                now,
                now,
            ),
        )
        refresh_fact_fts(fact_id, conn=conn)
    return fact_id


def add_evidence(fact_id: str, items: Sequence[Dict[str, Any]]) -> None:
    if not items:
        return
    with tx() as conn:
        for item in items:
            evidence_id = item.get("evidence_id") or secrets.token_hex(12)
            conn.execute(
                """
                INSERT OR REPLACE INTO fact_evidence(
                    evidence_id, fact_id, quote, who_said_id, who_said_label, ts_start_ms, utterance_ids, char_span, card_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    fact_id,
                    item.get("quote"),
                    item.get("who_said_id"),
                    item.get("who_said_label"),
                    item.get("ts_start_ms"),
                    json.dumps(item.get("utterance_ids")) if item.get("utterance_ids") is not None else None,
                    item.get("char_span"),
                    item.get("card_id"),
                ),
            )
        refresh_fact_fts(fact_id, conn=conn)


def link_entities(fact_id: str, links: Sequence[Dict[str, Any]]) -> None:
    if not links:
        return
    with tx() as conn:
        for link in links:
            entity_id = link.get("entity_id") or secrets.token_hex(12)
            org_id = link.get("org_id") or link.get("orgId") or link.get("org_id")
            if not org_id:
                fact_row = conn.execute(
                    "SELECT org_id FROM facts WHERE fact_id=?",
                    (fact_id,),
                ).fetchone()
                org_id = fact_row["org_id"] if fact_row else DEFAULT_ORG_ID
            conn.execute(
                """
                INSERT INTO entities(entity_id, org_id, type, display_name, external_ids, is_active)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    org_id=excluded.org_id,
                    type=excluded.type,
                    display_name=excluded.display_name,
                    external_ids=excluded.external_ids,
                    is_active=excluded.is_active
                """,
                (
                    entity_id,
                    org_id,
                    link.get("type") or link.get("role") or "unknown",
                    link.get("display_name") or link.get("name") or entity_id,
                    json.dumps(link.get("external_ids")) if link.get("external_ids") else None,
                    0 if link.get("is_active") in {False, 0, "0", "false"} else 1,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO fact_entities(fact_id, entity_id, role)
                VALUES(?, ?, ?)
                """,
                (
                    fact_id,
                    entity_id,
                    link.get("role"),
                ),
            )
        refresh_fact_fts(fact_id, conn=conn)


def _build_type_clause(types: Optional[Sequence[str]]) -> str:
    if not types:
        return ""
    placeholders = ",".join("?" for _ in types)
    return f" AND f.fact_type IN ({placeholders})"


def search_facts(org_id: str, query: Optional[str], types: Optional[Sequence[str]] = None, limit: int = 50) -> List[sqlite3.Row]:
    org_id = org_id or DEFAULT_ORG_ID
    with tx(readonly=True) as conn:
        params: List[Any] = [org_id]
        clause = _build_type_clause(types)
        if FTS_ENABLED and query:
            if types:
                params.extend(types)
            params.append(query)
            params.append(limit)
            sql = (
                "SELECT f.*, bm25(ft) AS fts_score FROM fact_fts ft JOIN facts f ON f.fact_id = ft.fact_id "
                "WHERE f.org_id=?" + clause + " AND fact_fts MATCH ? "
                "ORDER BY bm25(ft) ASC, f.created_at DESC LIMIT ?"
            )
            try:
                cur = conn.execute(sql, params)
                rows = cur.fetchall()
                if rows:
                    return rows
            except sqlite3.OperationalError:
                # Fallback to LIKE path if FTS MATCH syntax isn't supported in this environment
                pass
        needle = (query or '').strip()
        like = f"%{needle}%"
        params = [org_id]
        if types:
            params.extend(types)
        params.extend([needle, like, like, limit])
        sql = (
            "SELECT DISTINCT f.* FROM facts f "
            "LEFT JOIN fact_evidence e ON e.fact_id = f.fact_id "
            "WHERE f.org_id=?" + clause + " AND (? = '' OR f.payload LIKE ? OR e.quote LIKE ?) "
            "ORDER BY f.created_at DESC LIMIT ?"
        )
        return conn.execute(sql, params).fetchall()


def get_recent_facts(org_id: str, types: Optional[Sequence[str]] = None, limit: int = 100) -> List[sqlite3.Row]:
    org_id = org_id or DEFAULT_ORG_ID
    with tx(readonly=True) as conn:
        params: List[Any] = [org_id]
        clause = _build_type_clause(types)
        if types:
            params.extend(types)
        params.append(limit)
        sql = (
            "SELECT f.* FROM facts f WHERE f.org_id=?" + clause +
            " ORDER BY f.created_at DESC LIMIT ?"
        )
        return conn.execute(sql, params).fetchall()


def get_fact_rows(fact_ids: Sequence[str]) -> List[sqlite3.Row]:
    if not fact_ids:
        return []
    placeholders = ",".join("?" for _ in fact_ids)
    with tx(readonly=True) as conn:
        sql = f"SELECT * FROM facts WHERE fact_id IN ({placeholders})"
        return conn.execute(sql, list(fact_ids)).fetchall()


def get_evidence_for_fact_ids(fact_ids: Sequence[str]) -> Dict[str, List[sqlite3.Row]]:
    if not fact_ids:
        return {}
    placeholders = ",".join("?" for _ in fact_ids)
    with tx(readonly=True) as conn:
        sql = (
            "SELECT * FROM fact_evidence WHERE fact_id IN (" + placeholders + ")"
        )
        res: Dict[str, List[sqlite3.Row]] = {}
        for row in conn.execute(sql, list(fact_ids)).fetchall():
            res.setdefault(row["fact_id"], []).append(row)
        return res


def get_entities_for_fact_ids(fact_ids: Sequence[str]) -> Dict[str, List[sqlite3.Row]]:
    if not fact_ids:
        return {}
    placeholders = ",".join("?" for _ in fact_ids)
    with tx(readonly=True) as conn:
        sql = (
            "SELECT fe.fact_id, e.* FROM fact_entities fe "
            "JOIN entities e ON e.entity_id = fe.entity_id "
            "WHERE fe.fact_id IN (" + placeholders + ")"
        )
        res: Dict[str, List[sqlite3.Row]] = {}
        for row in conn.execute(sql, list(fact_ids)).fetchall():
            fact_id = row["fact_id"]
            res.setdefault(fact_id, []).append(row)
        return res


def get_agenda_proposals(org_id: str, limit: int = 20) -> List[sqlite3.Row]:
    with tx(readonly=True) as conn:
        cur = conn.execute(
            "SELECT * FROM agenda_proposals WHERE org_id=? ORDER BY created_at DESC LIMIT ?",
            (org_id or DEFAULT_ORG_ID, limit),
        )
        return cur.fetchall()


def update_fact_status(fact_id: str, status: str) -> None:
    if status not in ALLOWED_FACT_STATUSES:
        raise ValueError(f"Invalid status '{status}'")
    with tx() as conn:
        conn.execute(
            "UPDATE facts SET status=?, updated_at=? WHERE fact_id=?",
            (status, now_iso(), fact_id),
        )


def record_transcript(transcript: Dict[str, Any]) -> str:
    transcript_id = transcript.get("transcript_id") or secrets.token_hex(16)
    now = _normalize_datetime(transcript.get("created_at")) or now_iso()
    ensure_org(transcript.get("org_id") or DEFAULT_ORG_ID)
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO transcripts(transcript_id, org_id, meeting_id, source, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(transcript_id) DO UPDATE SET
                org_id=excluded.org_id,
                meeting_id=excluded.meeting_id,
                source=excluded.source,
                created_at=excluded.created_at
            """,
            (
                transcript_id,
                transcript.get("org_id") or DEFAULT_ORG_ID,
                transcript.get("meeting_id"),
                transcript.get("source"),
                now,
            ),
        )
    return transcript_id


def set_org_context(org_id: str, *, context_text: str, language: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
    org_id = org_id or DEFAULT_ORG_ID
    ensure_org(org_id)
    now = now_iso()
    meta_text = json.dumps(metadata) if metadata else None
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO org_context(org_id, language, context_text, metadata, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(org_id) DO UPDATE SET
                language=excluded.language,
                context_text=excluded.context_text,
                metadata=excluded.metadata,
                updated_at=excluded.updated_at
            """,
            (org_id, language, context_text, meta_text, now, now),
        )
        refresh_org_context_fts(org_id, conn=conn)


def get_org_context(org_id: str) -> Optional[sqlite3.Row]:
    org_id = org_id or DEFAULT_ORG_ID
    with tx(readonly=True) as conn:
        row = conn.execute(
            "SELECT org_id, language, context_text, metadata, created_at, updated_at FROM org_context WHERE org_id=?",
            (org_id,),
        ).fetchone()
        return row


def set_global_context(*, context_text: str, language: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, context_id: str = "default") -> None:
    now = now_iso()
    meta_text = json.dumps(metadata) if metadata else None
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO global_context(context_id, language, context_text, metadata, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(context_id) DO UPDATE SET
                language=excluded.language,
                context_text=excluded.context_text,
                metadata=excluded.metadata,
                updated_at=excluded.updated_at
            """,
            (context_id, language, context_text, meta_text, now, now),
        )
        refresh_global_context_fts(context_id, conn=conn)


def get_global_context(context_id: str = "default") -> Optional[sqlite3.Row]:
    with tx(readonly=True) as conn:
        row = conn.execute(
            "SELECT context_id, language, context_text, metadata, created_at, updated_at FROM global_context WHERE context_id=?",
            (context_id,),
        ).fetchone()
        return row
