"""
LangGraph research pipeline with a Critic → Writer feedback loop.

Graph topology:
  search_node → reader_node → writer_node → critic_node
                                  ↑               |
                                  └─── revise ────┘  (score < threshold AND revisions left)
                                                  |
                                                 END  (score >= threshold OR max revisions hit)
"""
import re
from langgraph.graph import StateGraph, END
import re as _re
from state import ResearchState
from agents import build_search_agent, build_reader_agent, writer_chain, critic_chain


def _agent_output(result: dict) -> str:
    """
    langgraph.prebuilt.create_react_agent returns {"messages": [...]}
    The last message contains the final answer.
    """
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return ""


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
            f"Search Results:\n{state['search_results']}"
        )]
    })
    return {"scraped_content": _agent_output(result)}


# ─────────────────────────────────────────────────────────────────────────────
# Node: Writer
# ─────────────────────────────────────────────────────────────────────────────
def writer_node(state: ResearchState) -> dict:
    revision_num = state.get("revision_num", 0)
    feedback = state.get("feedback", "")

    if revision_num == 0:
        print("\n[WRITER] Drafting initial report...")
        revision_instruction = ""
    else:
        print(f"\n[WRITER] Revising report (revision #{revision_num})...")
        
        areas_match = _re.search(
            r"Areas to Improve[:\s]*(.*?)(?:One.line Verdict|$)",
            feedback, _re.DOTALL | _re.IGNORECASE
        )
        areas = areas_match.group(1).strip() if areas_match else feedback

        revision_instruction = (
            f"IMPORTANT — This is revision #{revision_num}. "
            f"Address each of these specific issues from the critic:\n\n"
            f"{areas}\n\n"
            f"Do not just add a sentence — restructure or expand the relevant sections."
        )

    scraped = state.get("scraped_content", "")
    if scraped.startswith("Tool error") or scraped.startswith("Unknown tool"):
        scraped = "(scraping failed — using search results only)"

    research_combined = (
        f"SEARCH RESULTS:\n{state['search_results']}\n\n"
        f"DETAILED SCRAPED CONTENT:\n{scraped}"   # ← use scraped, not state['scraped_content']
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
    """
    Flexible score extraction. Handles formats Mistral commonly produces:
      Score: 7/10  |  **Score: 7/10**  |  Score: 7 out of 10  |  7/10
    """
    patterns = [
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+([\d.]+)\s*/\s*10",
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+([\d.]+)\s*out of\s*10",
        r"\*{0,2}[Ss]core\*{0,2}[:\s]+([\d.]+)",
        r"^([\d.]+)\s*/\s*10",
        r"([\d.]+)\s*/\s*10",
    ]
    for pattern in patterns:
        match = re.search(pattern, feedback_text, re.IGNORECASE | re.MULTILINE)
        if match:
            val = round(float(match.group(1)))

            if 0 <= val <= 10:
                return val
    return 5  # neutral fallback so we don't loop forever on parse failure


def critic_node(state: ResearchState) -> dict:
    print("\n[CRITIC] Reviewing report...")
    feedback = critic_chain.invoke({"report": state["report"]})
    print(f"[CRITIC] Raw feedback (first 300 chars):\n{feedback[:300]}\n")
    score = _parse_score(feedback)
    print(f"[CRITIC] Parsed score: {score}/10")
    return {"feedback": feedback, "critic_score": score}


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge
# ─────────────────────────────────────────────────────────────────────────────
def should_revise(state: ResearchState) -> str:
    score         = state.get("critic_score", 0)
    revision_num  = state.get("revision_num", 0)
    max_revisions = state.get("max_revisions", 3)
    score_threshold = state.get("score_threshold", 7)

    if score > score_threshold:
        print(f"\n[ROUTER] Score {score} > {score_threshold} → DONE ✓")
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

    builder.add_node("search", search_node)
    builder.add_node("reader", reader_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)

    builder.set_entry_point("search")
    builder.add_edge("search", "reader")
    builder.add_edge("reader", "writer")
    builder.add_edge("writer", "critic")

    builder.add_conditional_edges(
        "critic",
        should_revise,
        {"revise": "writer", "end": END},
    )

    return builder.compile()


research_graph = build_graph()