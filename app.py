"""
Streamlit app for the LangGraph research pipeline.
Shows live node progress and the critic→writer feedback loop.
"""

from dotenv import load_dotenv
load_dotenv()

import os
from supabase import create_client


import time
import streamlit as st

from graph import research_graph

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResearchMind · LangGraph",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: #e8e4dc; }
.stApp {
    background: #0a0a0f;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% -10%, rgba(255,140,50,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 110%, rgba(255,80,30,0.08) 0%, transparent 55%);
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 3rem 4rem; max-width: 1200px; }

.hero { text-align: center; padding: 3rem 0 2rem; }
.hero-eyebrow {
    font-family: 'DM Mono', monospace; font-size: 0.7rem; font-weight: 500;
    letter-spacing: 0.25em; text-transform: uppercase; color: #ff8c32;
    margin-bottom: 1rem;
}
.hero h1 {
    font-family: 'Syne', sans-serif; font-size: clamp(2.8rem, 6vw, 4.5rem);
    font-weight: 800; line-height: 1.0; letter-spacing: -0.03em;
    color: #f0ebe0; margin: 0 0 1rem;
}
.hero h1 span { color: #ff8c32; }
.hero-sub { font-size: 1rem; font-weight: 300; color: #a09890; max-width: 560px; margin: 0 auto; line-height: 1.65; }
.divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(255,140,50,0.3), transparent); margin: 2rem 0; }

.input-card {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,140,50,0.15);
    border-radius: 16px; padding: 2rem 2.5rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px);
}
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,140,50,0.25) !important;
    border-radius: 10px !important; color: #f0ebe0 !important;
    font-family: 'DM Sans', sans-serif !important; font-size: 1rem !important;
    padding: 0.75rem 1rem !important;
}
.stTextInput > div > div > input:focus { border-color: #ff8c32 !important; box-shadow: 0 0 0 3px rgba(255,140,50,0.12) !important; }
.stTextInput > label { font-family: 'DM Mono', monospace !important; font-size: 0.72rem !important; letter-spacing: 0.15em !important; text-transform: uppercase !important; color: #ff8c32 !important; }

.stButton > button {
    background: linear-gradient(135deg, #ff8c32 0%, #ff5a1a 100%) !important;
    color: #0a0a0f !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; font-size: 0.95rem !important; border: none !important;
    border-radius: 10px !important; padding: 0.7rem 2.2rem !important;
    box-shadow: 0 4px 20px rgba(255,140,50,0.3) !important; width: 100%;
}
.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 28px rgba(255,140,50,0.4) !important; }

/* ── Node cards ── */
.node-card {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px; padding: 1.2rem 1.5rem; margin-bottom: 0.8rem;
    position: relative; overflow: hidden;
}
.node-card.active  { border-color: rgba(255,140,50,0.45); background: rgba(255,140,50,0.04); }
.node-card.done    { border-color: rgba(80,200,120,0.3);  background: rgba(80,200,120,0.03); }
.node-card.revised { border-color: rgba(120,160,255,0.35); background: rgba(120,160,255,0.04); }
.node-card::before { content:''; position:absolute; left:0; top:0; bottom:0; width:3px; border-radius:14px 0 0 14px; background:rgba(255,255,255,0.05); }
.node-card.active::before  { background:#ff8c32; }
.node-card.done::before    { background:#50c878; }
.node-card.revised::before { background:#789aff; }

.node-header { display:flex; align-items:center; gap:0.8rem; }
.node-num  { font-family:'DM Mono',monospace; font-size:0.65rem; letter-spacing:0.15em; color:#ff8c32; opacity:0.75; }
.node-title{ font-family:'Syne',sans-serif; font-size:0.9rem; font-weight:700; color:#f0ebe0; }
.node-badge{ margin-left:auto; font-family:'DM Mono',monospace; font-size:0.65rem; letter-spacing:0.08em; }
.badge-wait{ color:#444; }
.badge-run { color:#ff8c32; }
.badge-done{ color:#50c878; }
.badge-loop{ color:#789aff; }

/* ── Revision badge ── */
.rev-badge {
    display:inline-block; background:rgba(120,160,255,0.12); border:1px solid rgba(120,160,255,0.25);
    border-radius:6px; padding:0.15rem 0.5rem; font-family:'DM Mono',monospace;
    font-size:0.65rem; color:#789aff; letter-spacing:0.1em; margin-top:0.4rem;
}

/* ── Score bar ── */
.score-bar-wrap { margin-top:0.6rem; }
.score-label { font-family:'DM Mono',monospace; font-size:0.65rem; color:#a09890; margin-bottom:0.25rem; }
.score-bar-bg { background:rgba(255,255,255,0.06); border-radius:4px; height:6px; }
.score-bar-fill { border-radius:4px; height:6px; transition: width 0.4s; }

.result-panel {
    background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.07);
    border-radius:14px; padding:1.5rem 2rem; margin-top:1rem; margin-bottom:1.2rem;
}
.result-panel-title { font-family:'DM Mono',monospace; font-size:0.7rem; letter-spacing:0.2em; text-transform:uppercase; color:#ff8c32; margin-bottom:1rem; padding-bottom:0.7rem; border-bottom:1px solid rgba(255,140,50,0.15); }
.result-content { font-size:0.88rem; line-height:1.8; color:#cdc8bf; white-space:pre-wrap; }

.report-panel { background:rgba(255,255,255,0.025); border:1px solid rgba(255,140,50,0.2); border-radius:16px; padding:2rem 2.5rem; margin-top:1rem; }
.feedback-panel { background:rgba(255,255,255,0.025); border:1px solid rgba(80,200,120,0.2); border-radius:16px; padding:2rem 2.5rem; margin-top:1rem; }
.panel-label { font-family:'DM Mono',monospace; font-size:0.7rem; letter-spacing:0.2em; text-transform:uppercase; margin-bottom:1.2rem; padding-bottom:0.7rem; }
.panel-label.orange { color:#ff8c32; border-bottom:1px solid rgba(255,140,50,0.15); }
.panel-label.green  { color:#50c878; border-bottom:1px solid rgba(80,200,120,0.15); }

.section-heading { font-family:'Syne',sans-serif; font-size:1.2rem; font-weight:700; color:#f0ebe0; margin:1.5rem 0 0.8rem; }
.notice { font-family:'DM Mono',monospace; font-size:0.68rem; color:#444; text-align:center; margin-top:3rem; letter-spacing:0.08em; }

/* slider label */
.stSlider > label { font-family:'DM Mono',monospace !important; font-size:0.7rem !important; letter-spacing:0.15em !important; text-transform:uppercase !important; color:#ff8c32 !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [
    ("pipeline_state", None),
    ("running", False),
    ("node_log", []),   # list of dicts: {node, revision, score}
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">LangGraph · Multi-Agent System</div>
  <h1>Research<span>Mind</span></h1>
  <p class="hero-sub">
    Four specialized agents connected by a <strong>LangGraph</strong> state machine.
    The Critic grades every draft and loops back to the Writer until the report
    clears your score target — or max revisions are hit.
  </p>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)


# ── Layout ─────────────────────────────────────────────────────────────────────
col_left, col_gap, col_right = st.columns([5, 0.4, 4])

with col_left:
    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    topic = st.text_input(
        "Research Topic",
        placeholder="e.g. Quantum computing breakthroughs in 2025",
        key="topic_input",
    )

    c1, c2 = st.columns(2)
    with c1:
        max_revisions = st.slider("Max Revisions", 1, 5, 3, key="max_rev")
    with c2:
        score_threshold = st.slider("Score Target (/10)", 5, 10, 7, key="score_thr")

    run_btn = st.button("⚡ Run LangGraph Pipeline", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Pipeline sidebar (right column) ───────────────────────────────────────────
def score_color(score: int) -> str:
    if score >= 8: return "#50c878"
    if score >= 6: return "#ff8c32"
    return "#e05555"


def render_pipeline_nodes(node_log: list, running_node: str = ""):
    """Render the node cards based on what's been logged so far."""
    NODES = [
        ("01", "search",  "Search Agent",  "Web search via Tavily"),
        ("02", "reader",  "Reader Agent",  "Scrape & extract content"),
        ("03", "writer",  "Writer Chain",  "Draft / revise report"),
        ("04", "critic",  "Critic Chain",  "Score & give feedback"),
    ]

    completed = {e["node"] for e in node_log}
    writer_revisions = sum(1 for e in node_log if e["node"] == "writer")
    latest_score = next(
        (e["score"] for e in reversed(node_log) if e.get("score") is not None), None
    )

    for num, key, title, desc in NODES:
        is_done = key in completed
        is_active = (key == running_node)
        is_revised = (key == "writer" and writer_revisions > 1)

        if is_active:
            card_cls, badge_cls, badge_txt = "active", "badge-run", "&#9679; RUNNING"
        elif is_done and is_revised:
            card_cls, badge_cls, badge_txt = "revised", "badge-loop", f"&#8634; &times;{writer_revisions}"
        elif is_done:
            card_cls, badge_cls, badge_txt = "done", "badge-done", "&#10003; DONE"
        else:
            card_cls, badge_cls, badge_txt = "", "badge-wait", "WAITING"

        revision_html = ""
        if key == "writer" and writer_revisions > 1:
            revision_html = f'<div class="rev-badge">Revision {writer_revisions - 1}</div>'

        score_html = ""
        if key == "critic" and is_done and latest_score is not None:
            color = score_color(latest_score)
            pct = latest_score * 10
            score_html = (
                '<div style="margin-top:0.6rem;">'
                f'<div style="font-family:monospace;font-size:0.65rem;color:#a09890;margin-bottom:0.25rem;">Latest score: {latest_score}/10</div>'
                f'<div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;width:100%;display:block;overflow:hidden;">'
                f'<div style="display:block;width:{pct}%;height:6px;min-height:6px;background:{color};border-radius:4px;"></div>'
                '</div>'
                '</div>'
            )

        html = (
            f'<div class="node-card {card_cls}">'
            f'<div class="node-header">'
            f'<span class="node-num">{num}</span>'
            f'<span class="node-title">{title}</span>'
            f'<span class="node-badge {badge_cls}">{badge_txt}</span>'
            f'</div>'
            f'<div style="font-size:0.78rem;color:#605850;margin-top:0.25rem;">{desc}</div>'
            f'{revision_html}'
            f'{score_html}'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


with col_right:
    st.markdown('<div class="section-heading">Graph Nodes</div>', unsafe_allow_html=True)
    node_placeholder = st.empty()

    with node_placeholder.container():
        render_pipeline_nodes(
            st.session_state.node_log or [],
            running_node="" if not st.session_state.running else "",
        )


# ── Trigger run ────────────────────────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.warning("Please enter a research topic first.")
    else:
        st.session_state.pipeline_state = None
        st.session_state.running = True
        st.session_state.node_log = []
        st.rerun()


# ── Stream graph execution ─────────────────────────────────────────────────────
if st.session_state.running:

    initial_state = {
        "topic": topic,
        "search_results": "",
        "scraped_content": "",
        "report": "",
        "feedback": "",
        "revision_num": 0,
        "max_revisions": st.session_state.max_rev,
        "critic_score": 0,
        "score_threshold": st.session_state.score_thr,
        "messages": [],
    }

    node_log = []
    final_state = None

    # Stream node-by-node so we can update the UI live
    for step in research_graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in step.items():
            score = node_output.get("critic_score", None)
            entry = {"node": node_name, "score": score}
            node_log.append(entry)
            st.session_state.node_log = list(node_log)

            # Refresh the right column live
            with node_placeholder.container():
                render_pipeline_nodes(node_log, running_node="")

            # Track merged state
            if final_state is None:
                final_state = {**initial_state, **node_output}
            else:
                final_state = {**final_state, **node_output}

    st.session_state.pipeline_state = final_state
    st.session_state.running = False
    st.rerun()


# ── Display results ────────────────────────────────────────────────────────────
ps = st.session_state.pipeline_state
if ps:
    with col_right:
        with node_placeholder.container():
            render_pipeline_nodes(st.session_state.node_log, running_node="")

        revs_used = ps.get("revision_num", 1) - 1
        final_score = ps.get("critic_score", 0)
        color = score_color(final_score)
        st.markdown(f"""
        <div style="margin-top:1rem;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:10px;padding:0.9rem 1.2rem;font-family:'DM Mono',monospace;font-size:0.72rem;">
          <span style="color:#a09890;">Final score </span>
          <span style="color:{color};font-weight:700;">{final_score}/10</span>
          &nbsp;·&nbsp;
          <span style="color:#a09890;">Revisions </span>
          <span style="color:#789aff;">{revs_used}/{st.session_state.max_rev}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Results</div>', unsafe_allow_html=True)

    if ps.get("search_results"):
        with st.expander("🔍 Search Results (raw)", expanded=False):
            st.markdown(f'<div class="result-panel"><div class="result-panel-title">Search Agent Output</div>'
                        f'<div class="result-content">{ps["search_results"]}</div></div>',
                        unsafe_allow_html=True)

    if ps.get("scraped_content"):
        with st.expander("📄 Scraped Content (raw)", expanded=False):
            st.markdown(f'<div class="result-panel"><div class="result-panel-title">Reader Agent Output</div>'
                        f'<div class="result-content">{ps["scraped_content"]}</div></div>',
                        unsafe_allow_html=True)

    if ps.get("report"):
        st.markdown('<div class="report-panel"><div class="panel-label orange">📝 Final Research Report</div>',
                    unsafe_allow_html=True)
        st.markdown(ps["report"])
        st.markdown("</div>", unsafe_allow_html=True)

        st.download_button(
            label="⬇ Download Report (.md)",
            data=ps["report"],
            file_name=f"research_report_{int(time.time())}.md",
            mime="text/markdown",
        )

    if ps.get("feedback"):
        st.markdown('<div class="feedback-panel"><div class="panel-label green">🧐 Critic Feedback</div>',
                    unsafe_allow_html=True)
        st.markdown(ps["feedback"], unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="notice">
  ResearchMind · LangGraph multi-agent pipeline · Streamlit
</div>
""", unsafe_allow_html=True)
