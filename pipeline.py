"""
CLI runner for the LangGraph research pipeline.
Usage:  python pipeline.py
"""
from graph import research_graph


def run_research_pipeline(
    topic: str,
    max_revisions: int = 3,
    score_threshold: int = 8,
) -> dict:
    initial_state = {
        "topic": topic,
        "search_results": "",
        "scraped_content": "",
        "report": "",
        "feedback": "",
        "revision_num": 0,
        "max_revisions": max_revisions,
        "critic_score": 0,
        "score_threshold": score_threshold,
        "messages": [],
    }

    print(f"\n{'='*60}")
    print(f"  ResearchMind · LangGraph Pipeline")
    print(f"  Topic         : {topic}")
    print(f"  Max revisions : {max_revisions}")
    print(f"  Score target  : {score_threshold}/10")
    print(f"{'='*60}")

    final_state = research_graph.invoke(initial_state)

    print(f"\n{'='*60}")
    print("  FINAL REPORT")
    print(f"{'='*60}")
    print(final_state["report"])

    print(f"\n{'='*60}")
    print(f"  CRITIC FEEDBACK  (score: {final_state['critic_score']}/10)")
    print(f"{'='*60}")
    print(final_state["feedback"])

    print(f"\n  Revisions used: {final_state['revision_num'] - 1} / {max_revisions}")
    return final_state


if __name__ == "__main__":
    topic = input("\nEnter a research topic: ").strip()
    run_research_pipeline(topic)
