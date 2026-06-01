"""
Shared state for the LangGraph research pipeline.

All nodes read from and write to this TypedDict.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ResearchState(TypedDict):
    # ── input ──────────────────────────────────────────────
    topic: str

    # ── intermediate outputs ────────────────────────────────
    search_results: str
    scraped_content: str
    report: str
    feedback: str

    # ── feedback-loop control ───────────────────────────────
    revision_num: int        # how many times writer has revised
    max_revisions: int       # cap (e.g. 3) to avoid infinite loops
    critic_score: int        # parsed 0-10 score from critic
    score_threshold: int     # minimum score to stop looping (e.g. 7)

    # ── Supabase memory ─────────────────────────────────────
    memory_hit: bool         # True if a similar past report was found
    memory_id: Optional[str] # UUID of the matched / newly-saved row
    memory_similarity: float # cosine similarity score of the cache hit (0–1)

    # ── agent message history (append-only via add_messages) ─
    messages: Annotated[list[BaseMessage], add_messages]