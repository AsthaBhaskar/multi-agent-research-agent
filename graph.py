"""
LangGraph research pipeline with Supabase memory + Critic → Writer feedback loop.

Graph topology (with memory):

    memory_check_node
        │
        ├─ cache_hit  ──────────────────────────────────────► writer_node
        │                                                          │
        └─ no_cache ──► search_node ──► reader_node ──► writer_node
                                                                   │
                                                             critic_node
                                                                   │
                                              ┌────── revise ──────┘
                                              │
                                           writer_node
                                              │
                                         (score OK / max revisions)
                                              │
                                     save_to_memory_node ──► END

Memory path skips search + reader entirely — the writer receives the
cached report as its "first draft" so the critic only needs light polish.
"""

import re
from langgraph.graph import StateGraph, END

from state import ResearchState
from agents import build_search_agent, build_reader_agent, writer_chain, critic_chain
from memory import find_similar, save_research


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def _agent_output(result: dict) -> str:
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Node: Memory Check  (NEW — fires before everything else)
# ─────────────────────────────────────────────────────────────────────────────

def memory_check_node(state: ResearchState) -> dict:
    print("\n[MEMORY] Checking Supabase for similar past research...")

    hit = find_similar(state["topic"])

    if hit:
        print(
            f"[MEMORY] ✓ Cache hit (similarity={hit.similarity:.3f}, "
            f"score={hit.critic_score}/10). Loading cached report."
        )
        return {
            "memory_hit": True,
            "memory_id": hit.id,
            "memory_similarity": hit.similarity,
            # Pre-populate report so writer_node can use it as a starting draft.
            "report": hit.report,
            # Provide stub values so downstream nodes that read these fields
            # don't blow up on a KeyError.
            "search_results": f"[LOADED FROM MEMORY — original topic: {hit.topic}]",
            "scraped_content": "[LOADED FROM MEMORY]",
            "revision_num": 0,
        }

    print("[MEMORY] No suitable cache hit. Running full pipeline.")
    return {
        "memory_hit": False,
        "memory_id": None,
        "memory_similarity": 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node: Search
# ─────────────────────────────────────────────────────────────────────────────

def search_node(state: ResearchState) -> dict:
    print("\n[SEARCH] Agent gathering web info...")
    agent = build_search_agent()
    result = agent.invoke({
        "messages": [("user", f"Find recent, reliable and detailed information about: {state['topic']}")]
    })
    return {"search_results": _agent_output(result)}


# ─────────────────────────────────────────────────────────────────────────────
# Node: Reader
# ─────────────────────────────────────────────────────────────────────────────

def reader_node(state: ResearchState) -> dict:
    print("\n[READER] Agent scraping top resources...")
    agent = build_reader_agent()
    result = agent.invoke({
        "messages": [(
            "user",
            f"Based on the following search results about '{state['topic']}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    })
    return {"scraped_content": _agent_output(result)}


# ─────────────────────────────────────────────────────────────────────────────
# Node: Writer
# ─────────────────────────────────────────────────────────────────────────────

def writer_node(state: ResearchState) -> dict:
    revision_num = state.get("revision_num", 0)
    feedback = state.get("feedback", "")
    memory_hit = state.get("memory_hit", False)

    if revision_num == 0 and memory_hit:
        print("\n[WRITER] Refining cached report for current topic...")
        revision_instruction = (
            "You have been given a high-quality report on a closely related topic. "
            "Your job is to adapt and update it specifically for the current query. "
            "Keep all accurate information, remove anything irrelevant, and add any "
            "necessary context to address the user's exact question."
        )
    elif revision_num == 0:
        print("\n[WRITER] Drafting initial report...")
        revision_instruction = ""
    else:
        print(f"\n[WRITER] Revising report (revision #{revision_num})...")
        revision_instruction = (
            f"IMPORTANT — This is revision #{revision_num}. "
            f"The critic gave the following feedback on your previous draft:\n\n"
            f"{feedback}\n\n"
            f"Address every area-to-improve listed above. Make the report significantly better."
        )

    research_combined = (
        f"SEARCH RESULTS:\n{state.get('search_results', '')}\n\n"
        f"DETAILED SCRAPED CONTENT:\n{state.get('scraped_content', '')}"
    )

    report = writer_chain.invoke({
        "topic": state["topic"],
        "research": research_combined,
        "revision_instruction": revision_instruction,
    })

    return {
        "report": report,
        "revision_num": revision_num + 1,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node: Critic
# ─────────────────────────────────────────────────────────────────────────────

def _parse_score(feedback_text: str) -> int:
    patterns = [
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+(\d+)\s*/\s*10",
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+(\d+)\s*out of\s*10",
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+(\d+)",
        r"^(\d+)\s*/\s*10",
        r"(\d+)\s*/\s*10",
    ]
    for pattern in patterns:
        match = re.search(pattern, feedback_text, re.IGNORECASE | re.MULTILINE)
        if match:
            val = int(match.group(1))
            if 0 <= val <= 10:
                return val
    return 5


def critic_node(state: ResearchState) -> dict:
    print("\n[CRITIC] Reviewing report...")
    feedback = critic_chain.invoke({"report": state["report"]})
    print(f"[CRITIC] Raw feedback (first 300 chars):\n{feedback[:300]}\n")
    score = _parse_score(feedback)
    print(f"[CRITIC] Parsed score: {score}/10")
    return {"feedback": feedback, "critic_score": score}


# ─────────────────────────────────────────────────────────────────────────────
# Node: Save to Memory  (NEW — fires once pipeline is done)
# ─────────────────────────────────────────────────────────────────────────────

def save_to_memory_node(state: ResearchState) -> dict:
    """
    Persist the final approved report to Supabase.

    If this run was served from the cache (memory_hit=True) we still save
    the *refined* version under the new topic so future queries can find it.
    """
    memory_hit = state.get("memory_hit", False)
    existing_id = state.get("memory_id")

    if memory_hit:
        print(
            f"\n[MEMORY] Saving refined report for new topic '{state['topic']}' "
            f"(derived from cached id={existing_id!r})..."
        )
    else:
        print(f"\n[MEMORY] Saving new research for topic '{state['topic']}'...")

    new_id = save_research(
        topic=state["topic"],
        report=state["report"],
        critic_score=state.get("critic_score", 0),
        search_results=state.get("search_results", ""),
        scraped_content=state.get("scraped_content", ""),
    )

    return {"memory_id": new_id}


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edges
# ─────────────────────────────────────────────────────────────────────────────

def route_after_memory_check(state: ResearchState) -> str:
    """Skip search+reader when we have a good cache hit."""
    if state.get("memory_hit", False):
        print("[ROUTER] Memory hit → skipping search & reader, going straight to writer.")
        return "use_cache"
    return "run_pipeline"


def should_revise(state: ResearchState) -> str:
    score = state.get("critic_score", 0)
    revision_num = state.get("revision_num", 0)
    max_revisions = state.get("max_revisions", 3)
    score_threshold = state.get("score_threshold", 7)

    if score >= score_threshold:
        print(f"\n[ROUTER] Score {score} >= {score_threshold} → DONE ✓")
        return "end"
    if revision_num >= max_revisions:
        print(f"\n[ROUTER] Max revisions ({max_revisions}) reached → DONE")
        return "end"

    print(f"\n[ROUTER] Score {score} < {score_threshold}, revision {revision_num}/{max_revisions} → REVISE")
    return "revise"


# ─────────────────────────────────────────────────────────────────────────────
# Build graph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(ResearchState)

    # ── nodes ──────────────────────────────────────────────────────────────
    builder.add_node("memory_check", memory_check_node)
    builder.add_node("search", search_node)
    builder.add_node("reader", reader_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("save_memory", save_to_memory_node)

    # ── entry ───────────────────────────────────────────────────────────────
    builder.set_entry_point("memory_check")

    # ── memory router ───────────────────────────────────────────────────────
    builder.add_conditional_edges(
        "memory_check",
        route_after_memory_check,
        {
            "use_cache": "writer",     # skip search + reader
            "run_pipeline": "search",  # full fresh run
        },
    )

    # ── fresh-run path ──────────────────────────────────────────────────────
    builder.add_edge("search", "reader")
    builder.add_edge("reader", "writer")

    # ── review loop ─────────────────────────────────────────────────────────
    builder.add_edge("writer", "critic")
    builder.add_conditional_edges(
        "critic",
        should_revise,
        {"revise": "writer", "end": "save_memory"},
    )

    # ── persist & finish ────────────────────────────────────────────────────
    builder.add_edge("save_memory", END)

    return builder.compile()


research_graph = build_graph()