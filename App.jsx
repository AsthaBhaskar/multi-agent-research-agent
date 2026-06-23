/**
 * ResearchMind — React UI for the LangGraph Multi-Agent Pipeline
 *
 * Drop this into src/App.jsx of a fresh Vite or CRA project.
 * The backend (backend.py) must be running on http://localhost:8000
 *
 * Fonts loaded via index.html or a <link> tag:
 *   https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&family=JetBrains+Mono:wght@300;400;500&display=swap
 */

import { useState, useRef, useEffect, useCallback } from "react";

// ── Constants ────────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const NODES = [
  { id: "search", label: "Search Agent",  desc: "Web search via Tavily",          icon: "⟳" },
  { id: "reader", label: "Reader Agent",  desc: "Scrape & extract content",       icon: "◈" },
  { id: "writer", label: "Writer Chain",  desc: "Draft / revise report",          icon: "◎" },
  { id: "critic", label: "Critic Chain",  desc: "Score & feedback",               icon: "◇" },
];

// ── Styles (CSS-in-JS object) ─────────────────────────────────────────────────
// Injected once via a <style> tag so we can use keyframes & pseudo-selectors.
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&family=JetBrains+Mono:wght@300;400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #09090d;
    --bg2:      #111117;
    --bg3:      #18181f;
    --bg4:      #222229;
    --line:     rgba(255,255,255,0.06);
    --line2:    rgba(255,255,255,0.11);
    --txt:      #edeae4;
    --txt2:     #8c8880;
    --txt3:     #44423e;
    --gold:     #d4a84b;
    --gold2:    #a07830;
    --golddim:  rgba(212,168,75,0.10);
    --goldglow: rgba(212,168,75,0.18);
    --teal:     #38c9a8;
    --tealdim:  rgba(56,201,168,0.09);
    --blue:     #5b8ef5;
    --bluedim:  rgba(91,142,245,0.09);
    --red:      #d95f5f;
    --reddim:   rgba(217,95,95,0.09);
    --green:    #52c87a;
    --greendim: rgba(82,200,122,0.09);
    --r:        10px;
    --rlg:      16px;
  }

  html, body, #root {
    height: 100%;
    background: var(--bg);
    color: var(--txt);
    font-family: 'DM Sans', sans-serif;
  }

  body {
    background:
      radial-gradient(ellipse 65% 45% at 10% 0%,   rgba(212,168,75,0.06) 0%, transparent 55%),
      radial-gradient(ellipse 45% 55% at 92% 100%,  rgba(56,201,168,0.04) 0%, transparent 50%),
      var(--bg);
  }

  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--bg4); border-radius: 3px; }

  @keyframes spin  { to { transform: rotate(360deg); } }
  @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.25;} }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes drawLine {
    from { stroke-dashoffset: 200; }
    to   { stroke-dashoffset: 0; }
  }

  .fadeUp { animation: fadeUp 0.35s ease both; }

  /* textarea / input reset */
  textarea, input[type=text], input[type=range] {
    font-family: 'DM Sans', sans-serif;
    color: var(--txt);
    background: var(--bg3);
    border: 1px solid var(--line2);
    border-radius: var(--r);
    outline: none;
    transition: border-color .2s, box-shadow .2s;
  }
  textarea:focus, input[type=text]:focus {
    border-color: rgba(212,168,75,.4);
    box-shadow: 0 0 0 3px rgba(212,168,75,.07);
  }
  textarea { resize: none; width: 100%; padding: .8rem 1rem; font-size: .95rem; line-height: 1.6; }

  input[type=range] {
    -webkit-appearance: none; appearance: none;
    width: 100%; height: 4px; background: var(--bg4);
    border: none; border-radius: 2px; cursor: pointer; padding: 0;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 15px; height: 15px;
    border-radius: 50%; background: var(--gold); cursor: pointer;
    box-shadow: 0 0 0 3px rgba(212,168,75,.18);
  }

  button { cursor: pointer; border: none; font-family: 'DM Sans', sans-serif; }
`;

// ── Tiny helpers ─────────────────────────────────────────────────────────────

function scoreColor(s) {
  if (s >= 8) return "var(--green)";
  if (s >= 6) return "var(--gold)";
  return "var(--red)";
}

function simpleMarkdown(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm,  "<h2>$1</h2>")
    .replace(/^# (.+)$/gm,   "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>")
    .replace(/^---$/gm, "<hr/>")
    .replace(/\n\n+/g, "</p><p>")
    .replace(/\n/g, "<br/>")
    .replace(/^/, "<p>").replace(/$/, "</p>")
    .replace(/<p>(<h[123]>)/g, "$1")
    .replace(/(<\/h[123]>)<\/p>/g, "$1")
    .replace(/<p>(<ul>)/g, "$1").replace(/(<\/ul>)<\/p>/g, "$1")
    .replace(/<p><hr\/><\/p>/g, "<hr/>");
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Mono({ children, style = {} }) {
  return (
    <span style={{ fontFamily: "'JetBrains Mono', monospace", ...style }}>
      {children}
    </span>
  );
}

function Label({ children }) {
  return (
    <Mono style={{
      fontSize: ".62rem", letterSpacing: ".18em", textTransform: "uppercase",
      color: "var(--txt3)", display: "block", marginBottom: ".45rem",
    }}>
      {children}
    </Mono>
  );
}

function Panel({ children, style = {}, accent }) {
  return (
    <div style={{
      background: "var(--bg2)",
      border: `1px solid ${accent || "var(--line)"}`,
      borderRadius: "var(--rlg)",
      overflow: "hidden",
      ...style,
    }}>
      {children}
    </div>
  );
}

function PanelHead({ icon, label, right, accent = "var(--gold)" }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: ".7rem",
      padding: ".95rem 1.4rem",
      borderBottom: "1px solid var(--line)",
      background: "var(--bg3)",
    }}>
      <span style={{
        width: 26, height: 26, borderRadius: 6,
        background: `rgba(${accent === "var(--gold)" ? "212,168,75" : "56,201,168"},.12)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: ".8rem", color: accent,
      }}>{icon}</span>
      <Mono style={{ fontSize: ".65rem", letterSpacing: ".14em", textTransform: "uppercase", color: "var(--txt2)" }}>
        {label}
      </Mono>
      {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
    </div>
  );
}

// Pipeline SVG diagram
function PipelineDiagram({ nodeStates }) {
  const nodes = ["search", "reader", "writer", "critic", "end"];
  const labels = { search: "Search", reader: "Reader", writer: "Writer", critic: "Critic", end: "END" };

  function stateOf(id) {
    if (id === "end") return nodeStates.__done ? "done" : "wait";
    return nodeStates[id] || "wait";
  }

  function circleColor(st) {
    if (st === "running") return { fill: "rgba(212,168,75,.15)", stroke: "var(--gold)" };
    if (st === "done")    return { fill: "rgba(82,200,122,.12)", stroke: "var(--green)" };
    if (st === "revised") return { fill: "rgba(91,142,245,.12)", stroke: "var(--blue)" };
    if (st === "skipped") return { fill: "rgba(91,142,245,.08)", stroke: "rgba(91,142,245,.4)" };
    return { fill: "var(--bg4)", stroke: "rgba(255,255,255,.08)" };
  }

  const W = 540, cy = 46, r = 22, gap = W / (nodes.length + 1);

  return (
    <svg viewBox={`0 0 ${W} 92`} style={{ width: "100%", maxWidth: W, display: "block", margin: "0 auto" }}>
      {/* connecting lines */}
      {nodes.slice(0, -1).map((_, i) => {
        const x1 = gap * (i + 1) + r, x2 = gap * (i + 2) - r;
        return (
          <line key={i} x1={x1} y1={cy} x2={x2} y2={cy}
            stroke="rgba(255,255,255,0.07)" strokeWidth="1.5" />
        );
      })}
      {/* loop arrow back from critic to writer */}
      <path d={`M ${gap*4} ${cy+r} Q ${gap*3.5} ${cy+36} ${gap*3} ${cy+r}`}
        fill="none" stroke="rgba(91,142,245,.3)" strokeWidth="1.2"
        strokeDasharray="3 3" markerEnd="url(#arr)" />
      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="rgba(91,142,245,.5)" />
        </marker>
      </defs>
      <text x={gap * 3.5} y={cy + 52} textAnchor="middle"
        style={{ font: "500 .52rem 'JetBrains Mono', monospace", fill: "rgba(91,142,245,.6)", letterSpacing: ".06em" }}>
        revise
      </text>
      {/* circles */}
      {nodes.map((id, i) => {
        const cx = gap * (i + 1);
        const { fill, stroke } = circleColor(stateOf(id));
        const glow = stateOf(id) === "running";
        return (
          <g key={id}>
            {glow && <circle cx={cx} cy={cy} r={r + 6} fill="rgba(212,168,75,.07)" />}
            <circle cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth="1.5" />
            <text x={cx} y={cy + 4.5} textAnchor="middle"
              style={{ font: "600 .78rem 'JetBrains Mono', monospace", fill: stroke }}>
              {i + 1 <= 4 ? String(i + 1).padStart(2, "0") : "✓"}
            </text>
            <text x={cx} y={cy + r + 14} textAnchor="middle"
              style={{ font: ".58rem 'JetBrains Mono', monospace", fill: "var(--txt3)", letterSpacing: ".08em" }}>
              {labels[id].toUpperCase()}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// Node status card
function NodeCard({ node, state, writerRevisions, latestScore }) {
  const isRunning = state === "running";
  const isDone    = state === "done";
  const isRevised = state === "revised";
  const isSkipped = state === "skipped";

  const borderColor = isRunning ? "rgba(212,168,75,.35)"
                    : isDone    ? "rgba(82,200,122,.22)"
                    : isRevised ? "rgba(91,142,245,.28)"
                    : isSkipped ? "rgba(91,142,245,.15)"
                    : "var(--line)";

  const stripColor  = isRunning ? "var(--gold)"
                    : isDone    ? "var(--green)"
                    : isRevised ? "var(--blue)"
                    : isSkipped ? "rgba(91,142,245,.5)"
                    : "rgba(255,255,255,.06)";

  const badgeStyle  = isRunning ? { color: "var(--gold)",  background: "var(--golddim)", border: "1px solid rgba(212,168,75,.22)" }
                    : isDone    ? { color: "var(--green)", background: "var(--greendim)", border: "1px solid rgba(82,200,122,.2)" }
                    : isRevised ? { color: "var(--blue)",  background: "var(--bluedim)",  border: "1px solid rgba(91,142,245,.2)" }
                    : isSkipped ? { color: "rgba(91,142,245,.8)", background: "rgba(91,142,245,.1)", border: "1px solid rgba(91,142,245,.2)" }
                    : { color: "var(--txt3)" };

  const badgeText   = isRunning ? "● RUNNING"
                    : isDone    ? "✓ DONE"
                    : isRevised ? `↺ ×${writerRevisions}`
                    : isSkipped ? "⊝ SKIPPED"
                    : "WAITING";

  const opacity = (!state || state === "wait") ? 0.38 : 1;

  return (
    <div style={{
      background: "var(--bg3)", border: `1px solid ${borderColor}`,
      borderRadius: "var(--r)", padding: ".85rem 1rem",
      position: "relative", overflow: "hidden",
      opacity, transition: "all .3s",
    }}>
      {/* left accent strip */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 3,
        borderRadius: "var(--r) 0 0 var(--r)", background: stripColor,
        transition: "background .3s",
      }} />

      <div style={{ display: "flex", alignItems: "center", gap: ".6rem", paddingLeft: 4 }}>
        <Mono style={{ fontSize: ".58rem", color: "var(--txt3)", letterSpacing: ".1em", minWidth: 18 }}>
          {node.id === "search" ? "01" : node.id === "reader" ? "02" : node.id === "writer" ? "03" : "04"}
        </Mono>
        <span style={{
          width: 24, height: 24, borderRadius: 5, background: "var(--bg4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: ".75rem", color: "var(--txt2)", flexShrink: 0,
        }}>
          {node.icon}
        </span>
        <span style={{ fontSize: ".85rem", fontWeight: 500, color: "var(--txt)" }}>{node.label}</span>
        <Mono style={{
          marginLeft: "auto", fontSize: ".58rem", letterSpacing: ".07em",
          padding: ".12rem .45rem", borderRadius: 100,
          ...badgeStyle,
        }}>
          {badgeText}
        </Mono>
      </div>
      <div style={{ fontSize: ".72rem", color: "var(--txt3)", marginTop: ".28rem", paddingLeft: 46 }}>
        {node.desc}
      </div>

      {/* revision pill */}
      {node.id === "writer" && writerRevisions > 1 && (
        <div style={{ paddingLeft: 46, marginTop: ".35rem" }}>
          <Mono style={{
            display: "inline-block", fontSize: ".58rem", letterSpacing: ".08em",
            color: "var(--blue)", background: "var(--bluedim)",
            border: "1px solid rgba(91,142,245,.18)", borderRadius: 100,
            padding: ".1rem .5rem",
          }}>
            Revision {writerRevisions - 1}
          </Mono>
        </div>
      )}

      {/* score bar */}
      {node.id === "critic" && latestScore > 0 && (
        <div style={{ paddingLeft: 46, marginTop: ".45rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: ".28rem" }}>
            <Mono style={{ fontSize: ".58rem", color: "var(--txt3)" }}>Quality score</Mono>
            <Mono style={{ fontSize: ".62rem", fontWeight: 500, color: scoreColor(latestScore) }}>
              {latestScore}/10
            </Mono>
          </div>
          <div style={{ height: 4, background: "var(--bg4)", borderRadius: 2 }}>
            <div style={{
              height: 4, borderRadius: 2, width: `${latestScore * 10}%`,
              background: scoreColor(latestScore), transition: "width .5s",
            }} />
          </div>
        </div>
      )}
    </div>
  );
}

// Collapsible raw output block
function RawBlock({ label, content, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!content) return null;
  return (
    <div className="fadeUp">
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: ".6rem",
          padding: ".7rem 1.1rem", background: "var(--bg3)",
          border: "1px solid var(--line2)", borderRadius: open ? "var(--r) var(--r) 0 0" : "var(--r)",
          color: "var(--txt2)", textAlign: "left", transition: "border-color .2s",
        }}
      >
        <Mono style={{ fontSize: ".62rem", letterSpacing: ".12em", textTransform: "uppercase" }}>{label}</Mono>
        <Mono style={{
          marginLeft: "auto", fontSize: ".56rem", background: "var(--bg4)",
          padding: ".1rem .35rem", borderRadius: 4,
        }}>RAW</Mono>
        <span style={{ fontSize: ".65rem", transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}>▼</span>
      </button>
      {open && (
        <div style={{
          background: "var(--bg2)", border: "1px solid var(--line2)", borderTop: "none",
          borderRadius: "0 0 var(--r) var(--r)", padding: "1rem 1.2rem",
          maxHeight: 260, overflowY: "auto",
        }}>
          <pre style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: ".72rem",
            color: "var(--txt2)", lineHeight: 1.75, whiteSpace: "pre-wrap", wordBreak: "break-word",
          }}>
            {content}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [topic, setTopic]             = useState("");
  const [maxRev, setMaxRev]           = useState(3);
  const [scoreThr, setScoreThr]       = useState(7);
  const [running, setRunning]         = useState(false);
  const [nodeStates, setNodeStates]   = useState({});       // { search: 'done', writer: 'running', … }
  const [writerRevs, setWriterRevs]   = useState(0);
  const [latestScore, setLatestScore] = useState(0);
  const [finalState, setFinalState]   = useState(null);
  const [logs, setLogs]               = useState([]);
  const [error, setError]             = useState("");
  const logRef = useRef(null);
  const eventSourceRef = useRef(null);

  // inject global CSS once
  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = GLOBAL_CSS;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const addLog = useCallback((msg, kind = "") => {
    const ts = new Date().toTimeString().slice(0, 8);
    setLogs(l => [...l, { ts, msg, kind }]);
  }, []);

  const resetState = useCallback(() => {
    setNodeStates({});
    setWriterRevs(0);
    setLatestScore(0);
    setFinalState(null);
    setLogs([]);
    setError("");
  }, []);

  const setNode = useCallback((id, st) => {
    setNodeStates(prev => ({ ...prev, [id]: st }));
  }, []);

  function runPipeline() {
    if (!topic.trim()) { setError("Please enter a research topic."); return; }
    resetState();
    setRunning(true);

    let revisionCount = 0;

    const cleanup = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setRunning(false);
    };

    const onNodeStart = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const n = payload.node;
        addLog(`[${n.toUpperCase()}] Starting…`, "gold");
        setNode(n, "running");
      } catch (err) {
        console.error(err);
      }
    };

    const onNodeDone = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const n = payload.node;
        const d = payload.data || {};

        // Check if this node was skipped (due to cache hit)
        if (d.status === "skipped") {
          setNode(n, "skipped");
          addLog(`[${n.toUpperCase()}] Skipped (cache hit)`, "blue");
          return;
        }

        if (n === "writer") {
          revisionCount++;
          setWriterRevs(revisionCount);
          setNode(n, revisionCount > 1 ? "revised" : "done");
          addLog(`[WRITER] Draft complete`, "green");
        } else if (n === "critic") {
          const sc = d.critic_score ?? 0;
          setLatestScore(sc);
          setNode(n, "done");
          addLog(`[CRITIC] Score: ${sc}/10`, sc >= scoreThr ? "green" : "blue");
        } else {
          setNode(n, "done");
          addLog(`[${n.toUpperCase()}] Done`, "green");
        }
      } catch (err) {
        console.error(err);
      }
    };

    const onPipelineEnd = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const fs = payload.final_state;
        setFinalState(fs);
        setNodeStates(prev => ({ ...prev, __done: true }));
        addLog("Pipeline complete ✓", "green");
      } catch (err) {
        console.error(err);
      }
      cleanup();
    };

    const onError = (e) => {
      let msg = "SSE connection error";
      if (e && typeof e.data === "string") {
        try {
          const payload = JSON.parse(e.data);
          msg = payload.message || msg;
        } catch (err) {
          console.warn("Unable to parse SSE error payload", err);
        }
      }
      console.warn("SSE connection error", msg, e);
      setError(msg);
      addLog(msg, "red");
      cleanup();
    };

    const params = new URLSearchParams({
      topic,
      max_revisions: String(maxRev),
      score_threshold: String(scoreThr),
    });
    const es = new EventSource(`${API_BASE}/api/research-stream?${params.toString()}`);
    eventSourceRef.current = es;

    es.addEventListener("node_start", onNodeStart);
    es.addEventListener("node_done", onNodeDone);
    es.addEventListener("pipeline_end", onPipelineEnd);
    es.addEventListener("error", onError);
    es.onopen = () => {
      console.debug("EventSource opened");
      addLog("SSE connection opened", "blue");
    };
  }

  const canRun = !running && topic.trim().length > 0;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 1260, margin: "0 auto", padding: "0 1.75rem 6rem" }}>

      {/* Nav */}
      <nav style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "1.5rem 0 2.5rem",
        borderBottom: "1px solid var(--line)",
        marginBottom: "3.5rem",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: ".55rem" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--gold)" }} />
          <span style={{ fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: "1.1rem", letterSpacing: "-.02em" }}>
            ResearchMind
          </span>
        </div>
        <div style={{ display: "flex", gap: ".45rem" }}>
          {["LangGraph", "Multi-Agent", "MistralAI"].map((t, i) => (
            <Mono key={t} style={{
              fontSize: ".58rem", letterSpacing: ".12em", textTransform: "uppercase",
              padding: ".28rem .7rem", borderRadius: 100,
              border: i === 0 ? "1px solid rgba(212,168,75,.3)" : "1px solid var(--line)",
              color: i === 0 ? "var(--gold)" : "var(--txt3)",
              background: i === 0 ? "var(--golddim)" : "transparent",
            }}>
              {t}
            </Mono>
          ))}
        </div>
      </nav>

      {/* Hero */}
      <div style={{ textAlign: "center", padding: "0 1rem 3.5rem" }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: ".5rem",
          marginBottom: "1.1rem",
        }}>
          <div style={{ flex: "0 0 24px", height: 1, background: "rgba(212,168,75,.3)" }} />
          <Mono style={{ fontSize: ".62rem", letterSpacing: ".22em", textTransform: "uppercase", color: "var(--gold)" }}>
            Critic · Writer Feedback Loop
          </Mono>
          <div style={{ flex: "0 0 24px", height: 1, background: "rgba(212,168,75,.3)" }} />
        </div>
        <h1 style={{
          fontFamily: "Syne, sans-serif", fontWeight: 800, fontSize: "clamp(2.8rem,7vw,5rem)",
          letterSpacing: "-.04em", lineHeight: .95, color: "var(--txt)", marginBottom: "1.2rem",
        }}>
          Research<span style={{ color: "var(--gold)" }}>Mind</span>
        </h1>
        <p style={{ fontSize: ".95rem", fontWeight: 300, color: "var(--txt2)", maxWidth: 520, margin: "0 auto", lineHeight: 1.7 }}>
          Four specialized agents connected by a LangGraph state machine. The Critic grades every draft
          and loops back to the Writer until the report clears your score target.
        </p>
      </div>

      {/* Pipeline diagram */}
      <Panel style={{ marginBottom: "2rem" }}>
        <PanelHead icon="⚡" label="Agent Pipeline" />
        <div style={{ padding: "1.5rem 1rem 1.75rem" }}>
          <PipelineDiagram nodeStates={nodeStates} />
        </div>
      </Panel>

      {/* Main grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 340px",
        gap: "1.75rem",
        alignItems: "start",
      }}>

        {/* Left column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

          {/* Config panel */}
          <Panel>
            <PanelHead icon="⚙" label="Configure Research" />
            <div style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>

                <div>
                  <Label>Research Topic</Label>
                  <textarea
                    rows={3}
                    placeholder="e.g. Quantum computing breakthroughs in 2025, Impact of LLMs on software engineering…"
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.2rem" }}>
                  {[
                    { id: "maxRev",  label: "Max Revisions",     val: maxRev,   set: setMaxRev,   min: 1, max: 5 },
                    { id: "scorThr", label: "Score Target (/10)", val: scoreThr, set: setScoreThr, min: 5, max: 10 },
                  ].map(({ id, label, val, set, min, max }) => (
                    <div key={id}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: ".45rem" }}>
                        <Label>{label}</Label>
                        <Mono style={{
                          fontSize: ".68rem", fontWeight: 500, color: "var(--gold)",
                          background: "var(--golddim)", border: "1px solid rgba(212,168,75,.2)",
                          borderRadius: 4, padding: ".1rem .38rem",
                        }}>
                          {val}
                        </Mono>
                      </div>
                      <input type="range" min={min} max={max} value={val} step={1}
                        onChange={e => set(Number(e.target.value))} />
                    </div>
                  ))}
                </div>

                {error && (
                  <div style={{
                    background: "var(--reddim)", border: "1px solid rgba(217,95,95,.25)",
                    borderRadius: "var(--r)", padding: ".65rem 1rem",
                    fontSize: ".82rem", color: "var(--red)",
                  }}>
                    {error}
                  </div>
                )}

                <button
                  disabled={!canRun}
                  onClick={runPipeline}
                  style={{
                    padding: ".9rem", borderRadius: "var(--r)",
                    background: canRun
                      ? "linear-gradient(135deg, var(--gold) 0%, var(--gold2) 100%)"
                      : "var(--bg4)",
                    color: canRun ? "var(--bg)" : "var(--txt3)",
                    fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: ".95rem",
                    boxShadow: canRun ? "0 6px 24px rgba(212,168,75,.28)" : "none",
                    transition: "all .2s",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: ".6rem",
                  }}
                >
                  {running ? (
                    <>
                      <div style={{
                        width: 15, height: 15, border: "2px solid rgba(0,0,0,.18)",
                        borderTopColor: "var(--bg)", borderRadius: "50%",
                        animation: "spin .7s linear infinite",
                      }} />
                      Running Pipeline…
                    </>
                  ) : (
                    <> ⚡ Run LangGraph Pipeline </>
                  )}
                </button>
              </div>
            </div>
          </Panel>

          {/* Agent log */}
          {logs.length > 0 && (
            <Panel className="fadeUp">
              <PanelHead
                icon="▸"
                label="Agent Log"
                right={
                  running && (
                    <div style={{
                      width: 6, height: 6, borderRadius: "50%", background: "var(--green)",
                      animation: "pulse 1.1s ease infinite",
                    }} />
                  )
                }
              />
              <div ref={logRef} style={{
                padding: ".9rem 1.2rem", maxHeight: 190, overflowY: "auto",
                fontFamily: "'JetBrains Mono', monospace", fontSize: ".7rem",
                lineHeight: 1.8, color: "var(--txt3)",
              }}>
                {logs.map((l, i) => (
                  <div key={i} style={{ display: "flex", gap: ".75rem" }}>
                    <span style={{ opacity: .45, flexShrink: 0 }}>{l.ts}</span>
                    <span style={{
                      color: l.kind === "gold"  ? "var(--gold)"
                           : l.kind === "green" ? "var(--green)"
                           : l.kind === "blue"  ? "var(--blue)"
                           : l.kind === "red"   ? "var(--red)"
                           : "var(--txt2)",
                    }}>
                      {l.msg}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {/* Results */}
          {!finalState && !running && logs.length === 0 && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "4rem 2rem", textAlign: "center", gap: ".7rem" }}>
              <div style={{ fontSize: "2.5rem", opacity: .18 }}>◎</div>
              <div style={{ fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: "1.2rem", color: "var(--txt)", opacity: .25 }}>
                No research yet
              </div>
              <p style={{ fontSize: ".8rem", color: "var(--txt3)", maxWidth: 260, lineHeight: 1.6 }}>
                Enter a topic and run the pipeline to see agents work live.
              </p>
            </div>
          )}

          {finalState && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }} className="fadeUp">

              {/* Raw outputs */}
              <RawBlock label="🔍 Search Results" content={finalState.search_results} />
              <RawBlock label="📄 Scraped Content" content={finalState.scraped_content} />

              {/* Report */}
              {finalState.report && (
                <Panel accent="rgba(212,168,75,.2)">
                  <PanelHead
                    icon="✎"
                    label="Final Research Report"
                    right={
                      <a
                        href={`data:text/markdown;charset=utf-8,${encodeURIComponent(finalState.report)}`}
                        download="research_report.md"
                        style={{
                          fontFamily: "'JetBrains Mono', monospace", fontSize: ".6rem",
                          letterSpacing: ".1em", textTransform: "uppercase",
                          color: "var(--txt2)", background: "var(--bg4)",
                          border: "1px solid var(--line2)", borderRadius: 6,
                          padding: ".35rem .7rem", textDecoration: "none",
                          transition: "color .15s",
                        }}
                      >
                        ⬇ .md
                      </a>
                    }
                  />
                  <div style={{ padding: "1.6rem 2rem" }}>
                    <div
                      style={{ fontSize: ".9rem", lineHeight: 1.85, color: "var(--txt2)" }}
                      dangerouslySetInnerHTML={{ __html: simpleMarkdown(finalState.report) }}
                    />
                  </div>
                </Panel>
              )}

              {/* Feedback */}
              {finalState.feedback && (
                <Panel accent="rgba(82,200,122,.18)">
                  <PanelHead icon="◇" label="Critic Feedback" accent="var(--green)" />
                  <div style={{ padding: "1.4rem 2rem" }}>
                    <div
                      style={{ fontSize: ".88rem", lineHeight: 1.8, color: "var(--txt2)" }}
                      dangerouslySetInnerHTML={{ __html: simpleMarkdown(finalState.feedback) }}
                    />
                  </div>
                </Panel>
              )}
            </div>
          )}
        </div>

        {/* Right column — agent status */}
        <div style={{ position: "sticky", top: "1.5rem" }}>
          <Panel>
            <PanelHead icon="◈" label="Agent Status" />
            <div style={{ padding: "1.2rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: ".65rem" }}>
                {NODES.map(node => (
                  <NodeCard
                    key={node.id}
                    node={node}
                    state={nodeStates[node.id] || "wait"}
                    writerRevisions={node.id === "writer" ? writerRevs : 0}
                    latestScore={node.id === "critic" ? latestScore : 0}
                  />
                ))}
              </div>

              {/* Summary stats */}
              {finalState && (
                <div className="fadeUp" style={{ marginTop: "1.1rem" }}>
                  <div style={{ height: 1, background: "var(--line)", margin: "0 0 1rem" }} />
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: ".6rem" }}>
                    {[
                      { label: "Score",     val: `${finalState.critic_score ?? 0}/10`, color: scoreColor(finalState.critic_score ?? 0) },
                      { label: "Revisions", val: `${Math.max(0, (finalState.revision_num ?? 1) - 1)}/${maxRev}`, color: "var(--blue)" },
                      { label: "Status",    val: (finalState.critic_score ?? 0) >= scoreThr ? "PASS" : "DONE", color: "var(--green)", small: true },
                    ].map(({ label, val, color, small }) => (
                      <div key={label} style={{
                        background: "var(--bg4)", borderRadius: "var(--r)",
                        padding: ".75rem .8rem",
                      }}>
                        <Mono style={{ fontSize: ".55rem", color: "var(--txt3)", letterSpacing: ".1em", textTransform: "uppercase", display: "block", marginBottom: ".3rem" }}>
                          {label}
                        </Mono>
                        <span style={{ fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: small ? ".85rem" : "1.3rem", color, lineHeight: 1 }}>
                          {val}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Panel>
        </div>

      </div>

      {/* Footer */}
      <footer style={{
        borderTop: "1px solid var(--line)", marginTop: "4rem", padding: "1.4rem 0",
        display: "flex", justifyContent: "space-between",
      }}>
        <Mono style={{ fontSize: ".58rem", color: "var(--txt3)", letterSpacing: ".06em" }}>
          ResearchMind · LangGraph Multi-Agent Pipeline
        </Mono>
        <Mono style={{ fontSize: ".58rem", color: "var(--txt3)", letterSpacing: ".06em" }}>
          Search → Reader → Writer → Critic → Loop
        </Mono>
      </footer>

    </div>
  );
}
