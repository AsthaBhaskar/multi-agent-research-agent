cat > /mnt/user-data/outputs/README.md << 'READMEEOF'
# 🔬 ResearchMind — Multi-Agent Research Pipeline

A LangGraph-powered multi-agent system that autonomously researches any topic, writes a structured report, and self-improves the draft through a **Critic → Writer feedback loop** until a quality score threshold is met.

Built with **LangGraph**, **Mistral AI**, **Tavily**, **Streamlit**, and **Supabase**.

---

## ✨ Features

- **4 specialized agents** orchestrated as a stateful LangGraph graph
- **Autonomous web search** via Tavily API
- **Deep content extraction** by scraping the most relevant URL found
- **AI-written reports** structured as Introduction / Key Findings / Conclusion / Sources
- **Self-critique loop** — the Critic scores every draft (0–10) and loops back to the Writer with targeted feedback until the score target is met or max revisions are exhausted
- **Supabase memory** — persistent storage of past research runs and report history
- **React frontend** — modern web UI alongside the Streamlit interface
- **Live Streamlit UI** with real-time node progress, score bars, and a markdown report download
- **CLI runner** for headless / scripted usage

---

## 🏗️ Architecture

```
User Input (topic)
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Search Node │────▶│ Reader Node │────▶│ Writer Node │◀─────┐
│  (Agent)    │     │  (Agent)    │     │  (Chain)    │      │
└─────────────┘     └─────────────┘     └─────────────┘      │
                                               │          revise
                                               ▼              │
                                        ┌─────────────┐       │
                                        │ Critic Node │───────┘
                                        │  (Chain)    │
                                        └─────┬───────┘
                                              │
                              score ≥ target OR max revisions hit
                                              │
                                              ▼
                                        ┌──────────┐
                                        │ Supabase │  ← persist report + feedback
                                        └──────────┘
                                              │
                                              ▼
                                     React UI / Streamlit
```

### Agent Topology (LangGraph)

| Step | Node | Type | Role |
|------|------|------|------|
| 1 | `search` | Tool-calling Agent | Queries Tavily for recent web results |
| 2 | `reader` | Tool-calling Agent | Picks the best URL, scrapes its content |
| 3 | `writer` | LLM Chain | Drafts (or revises) the research report |
| 4 | `critic` | LLM Chain | Scores the report and produces structured feedback |
| — | Router | Conditional Edge | Loops back to writer or exits to END |
| — | Supabase | Persistence Layer | Stores topic, report, score, feedback per run |

---

## 📁 Project Structure

```
multi-agent-research-agent/
│
│  ── Python Backend ──────────────────────────────────────────
├── state.py          # ResearchState TypedDict — shared memory across all nodes
├── tools.py          # LangChain @tools: web_search (Tavily) + scrape_url (BeautifulSoup)
├── agents.py         # LLM agents (bind_tools + manual agentic loop), writer & critic chains
├── graph.py          # LangGraph StateGraph: nodes, edges, conditional router, compiled graph
├── pipeline.py       # CLI runner — invokes the graph and pretty-prints results
├── app.py            # Streamlit UI — live node cards, score bar, report + feedback display
│
│  ── Persistence ─────────────────────────────────────────────
├── memory.py         # Supabase client — save/load research runs from Postgres
│
│  ── React Frontend ──────────────────────────────────────────
├── frontend/         # React app (Vite / CRA)
│   ├── src/
│   │   ├── components/   # NodeCard, ReportPanel, FeedbackPanel, ScoreBar
│   │   ├── pages/        # Home, History, ReportDetail
│   │   └── lib/          # Supabase client, API hooks
│   └── package.json
│
├── requirements.txt  # Python dependencies (includes supabase>=2.4.0)
└── .env              # API keys (not committed — see .env.example)
```

> **Note:** The React frontend and `memory.py` Supabase integration are under active development. The `supabase>=2.4.0` dependency is already declared in `requirements.txt`.

---

## 🗄️ Supabase Memory Layer

Research runs are persisted to a Supabase Postgres table so you can browse, compare, and revisit past reports.

### Schema

```sql
create table research_runs (
  id          uuid primary key default gen_random_uuid(),
  topic       text not null,
  report      text,
  feedback    text,
  score       int,
  revisions   int,
  created_at  timestamptz default now()
);
```

### Usage (Python)

```python
from memory import save_run, load_runs

# After pipeline completes:
save_run(topic, report, feedback, score, revisions)

# Retrieve history:
runs = load_runs(limit=10)
```

---

## 🔄 Execution Flow

1. User enters a **topic**, sets **max revisions** (1–5) and **score target** (5–10)
2. **Search Agent** runs a Tavily query — results stored as `search_results`
3. **Reader Agent** picks the most relevant URL and scrapes it — stored as `scraped_content`
4. **Writer Chain** combines both sources, generates a structured report — `revision_num` increments
5. **Critic Chain** scores the report (0–10) with structured feedback (Strengths / Areas to Improve / Verdict)
6. **Router** checks `critic_score` vs `score_threshold` and `revision_num` vs `max_revisions`:
   - If score < threshold **and** revisions remain → loop back to Writer with feedback injected as `revision_instruction`
   - Otherwise → END
7. Final report + feedback + score are **saved to Supabase** for history

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the React frontend)
- A [Mistral AI API key](https://console.mistral.ai/)
- A [Tavily API key](https://app.tavily.com/)
- A [Supabase project](https://supabase.com/) with the schema above applied

### Installation

```bash
git clone https://github.com/dramaaa98/multi-agent-research-agent.git
cd multi-agent-research-agent

# Python backend
pip install -r requirements.txt

# React frontend
cd frontend
npm install
```

### Environment Variables

Create `.env` in the project root (never commit this):

```env
MISTRAL_API_KEY=your_mistral_key_here
TAVILY_API_KEY=your_tavily_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_or_service_key
```

### Run the Streamlit UI

```bash
streamlit run app.py
```

Open `http://localhost:8501`.

### Run the React Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

### Run from the CLI

```bash
python pipeline.py
```

### Run programmatically

```python
from pipeline import run_research_pipeline

result = run_research_pipeline(
    topic="Advances in fusion energy 2025",
    max_revisions=3,
    score_threshold=8,
)
print(result["report"])
```

---

## 📦 Dependencies

### Python

| Package | Purpose |
|---------|---------|
| `langgraph>=0.2.0` | State machine / graph orchestration |
| `langchain-mistralai>=0.2.0` | Mistral LLM integration |
| `langchain-core` / `langchain>=0.3.0` | Prompts, parsers, message types |
| `tavily-python>=0.3.0` | Web search API |
| `beautifulsoup4>=4.12.0` | HTML scraping & cleaning |
| `requests>=2.31.0` | HTTP fetching |
| `streamlit>=1.35.0` | Streamlit web UI |
| `supabase>=2.4.0` | Supabase Postgres persistence |
| `mistralai>=1.0.0` | Mistral native SDK |
| `python-dotenv>=1.0.0` | `.env` loading |
| `rich>=13.0.0` | CLI pretty-printing |

### React Frontend

| Package | Purpose |
|---------|---------|
| `react` / `vite` | UI framework and bundler |
| `@supabase/supabase-js` | Supabase client for report history |
| `tailwindcss` | Styling |

---

## ⚙️ Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_revisions` | 3 | Maximum Writer → Critic loops before forced exit |
| `score_threshold` | 7 | Minimum critic score (out of 10) to stop looping |
| LLM model | `mistral-small-latest` | Change in `agents.py` |
| Tavily `max_results` | 5 | Results per search query (`tools.py`) |
| Scrape char limit | 3 000 | Max chars from a scraped page (`tools.py`) |
| Search results to reader | 800 chars | Truncation in `graph.py` `reader_node` |

---

## 🔍 Code Analysis & Design Notes

### Strengths

- **Clean separation of concerns** — state, tools, agents, graph wiring, UI, and persistence are all isolated files with clear single responsibilities.
- **Version-compatible agent loop** — avoids `create_react_agent` in favour of a manual `_run_tool_agent()` loop (~20 lines) that works across LangGraph versions.
- **Robust score parsing** — five regex patterns in `_parse_score()` handle all the formatting variations Mistral produces (`Score: 7/10`, `**Score: 7/10**`, `7 out of 10`, etc.), with a neutral fallback of 5 to prevent infinite loops.
- **Streaming UI** — `research_graph.stream(stream_mode="updates")` renders live node progress without blocking Streamlit.
- **Feedback injection** — the writer receives the critic's full text in `revision_instruction`, making revisions genuinely targeted rather than blind re-attempts.
- **Persistent history via Supabase** — runs survive process restarts and can be browsed, compared, and recalled from the React frontend.

### Potential Improvements

- **`.env` committed to the public repo** — real API keys should never be in version control. Add `.env` to `.gitignore` and provide `.env.example` instead.
- **Only one URL scraped** per run. Scraping 2–3 URLs in parallel would give the writer richer source material.
- **`search_results[:800]`** passed to the reader is quite short; increasing to 1 500–2 000 chars would improve URL selection quality on verbose topics.
- **No async execution** — search and scrape are sequential; wrapping them with `asyncio` would reduce latency.
- **No error boundaries** around graph execution in `app.py` — an API failure mid-run surfaces as an unhandled Streamlit exception.
- **Hardcoded model string** — surface `MISTRAL_MODEL` as an env variable or UI selector to make model comparison easier.

---
