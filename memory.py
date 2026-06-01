"""
memory.py — Supabase-backed semantic memory for the research pipeline.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# ── config ────────────────────────────────────────────────────────────────────

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
MISTRAL_API_KEY: str = os.environ["MISTRAL_API_KEY"]

TABLE_NAME = "research_memory"
EMBEDDING_MODEL = "mistral-embed"
EMBEDDING_DIM = 1024

SIMILARITY_THRESHOLD: float = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.82"))
MAX_CACHE_AGE_DAYS: int = int(os.environ.get("MEMORY_MAX_AGE_DAYS", "30"))

# ── clients ───────────────────────────────────────────────────────────────────
# supabase-py v2 requires explicitly passing the service-role key as a Bearer
# token so it actually bypasses RLS. create_client alone is not sufficient.

_supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        auto_refresh_token=False,
        persist_session=False,
    ),
)
_mistral: Mistral = Mistral(api_key=MISTRAL_API_KEY)

# ── setup check ───────────────────────────────────────────────────────────────

_SETUP_OK: Optional[bool] = None


def _check_setup() -> bool:
    global _SETUP_OK
    if _SETUP_OK is not None:
        return _SETUP_OK

    # Check 1: table reachable
    try:
        _supabase.table(TABLE_NAME).select("id").limit(1).execute()
    except Exception as e:
        print(
            f"\n[MEMORY] ✗ Table '{TABLE_NAME}' not found or not reachable.\n"
            f"  → Make sure supabase_migration.sql was run successfully.\n"
            f"  → Error: {e}\n"
        )
        _SETUP_OK = False
        return False

    # Check 2: RPC function reachable
    try:
        probe_vec = _embed("setup probe")
        _supabase.rpc(
            "match_research_memory",
            {
                "query_embedding": probe_vec,
                "match_threshold": 0.9999,
                "match_count": 1,
            },
        ).execute()
    except Exception as e:
        err_str = str(e)
        if "PGRST125" in err_str or "Invalid path" in err_str:
            print(
                f"\n[MEMORY] ✗ RPC function 'match_research_memory' not found.\n"
                f"  → Run supabase_migration.sql in Supabase SQL Editor.\n"
            )
        elif "42501" in err_str or "permission denied" in err_str.lower():
            # RLS denial on probe = function exists, service-role key works
            print("[MEMORY] ✓ Supabase setup verified.")
            _SETUP_OK = True
            return True
        else:
            print(f"\n[MEMORY] ✗ Supabase error during setup check: {e}\n")
        _SETUP_OK = False
        return False

    print("[MEMORY] ✓ Supabase setup verified.")
    _SETUP_OK = True
    return True


# ── helpers ───────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    response = _mistral.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=[text.strip()],
    )
    return response.data[0].embedding


def _days_old(iso_timestamp: str) -> float:
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86_400


# ── public API ────────────────────────────────────────────────────────────────

class MemoryHit:
    def __init__(self, row: dict, similarity: float):
        self.id: str = row["id"]
        self.topic: str = row["topic"]
        self.report: str = row["report"]
        self.critic_score: int = row["critic_score"]
        self.created_at: str = row["created_at"]
        self.similarity: float = similarity

    def __repr__(self) -> str:
        return (
            f"<MemoryHit id={self.id!r} similarity={self.similarity:.3f} "
            f"score={self.critic_score} topic={self.topic!r}>"
        )


def find_similar(topic: str) -> Optional[MemoryHit]:
    if not _check_setup():
        print("[MEMORY] Skipping memory lookup — Supabase not reachable.")
        return None

    embedding = _embed(topic)
    response = _supabase.rpc(
        "match_research_memory",
        {
            "query_embedding": embedding,
            "match_threshold": SIMILARITY_THRESHOLD,
            "match_count": 1,
        },
    ).execute()

    rows = response.data
    if not rows:
        return None

    row = rows[0]
    similarity: float = row.get("similarity", 0.0)

    if MAX_CACHE_AGE_DAYS > 0:
        age = _days_old(row["created_at"])
        if age > MAX_CACHE_AGE_DAYS:
            print(f"[MEMORY] Cache hit too old ({age:.1f} days). Ignoring.")
            return None

    print(f"[MEMORY] Cache hit! similarity={similarity:.3f}, score={row['critic_score']}, topic={row['topic']!r}")
    return MemoryHit(row, similarity)


def save_research(
    topic: str,
    report: str,
    critic_score: int,
    search_results: str = "",
    scraped_content: str = "",
) -> str:
    if not _check_setup():
        print("[MEMORY] Skipping save — Supabase not reachable.")
        return ""

    embedding = _embed(topic)
    payload = {
        "topic": topic,
        "topic_embedding": embedding,
        "report": report,
        "critic_score": critic_score,
        "search_results": search_results,
        "scraped_content": scraped_content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    response = _supabase.table(TABLE_NAME).insert(payload).execute()
    row_id: str = response.data[0]["id"]
    print(f"[MEMORY] Saved research to Supabase. id={row_id!r}")
    return row_id