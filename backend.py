"""
FastAPI backend for the LangGraph research pipeline.
Replaces app.py (Streamlit).

Endpoints:
  POST /api/research          – run pipeline, returns SSE stream of node events
  GET  /api/health            – health check

Run:
  pip install fastapi uvicorn sse-starlette
  uvicorn backend:app --reload --port 8000

CORS is open to localhost:3000 (React dev server).
"""

import json
import os
import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Import `research_graph` lazily inside the pipeline runner to avoid heavy
# top-level imports that block server startup.

app = FastAPI(title="ResearchMind API")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "")
origins = (
    [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
    if ALLOWED_ORIGINS
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    topic: str
    max_revisions: int = 3
    score_threshold: int = 7


# ── SSE stream ────────────────────────────────────────────────────────────────

async def pipeline_stream(req: ResearchRequest) -> AsyncGenerator[dict, None]:
    """
    Streams Server-Sent Events as the LangGraph graph executes.

    Event types emitted:
      node_start   { node }
      node_done    { node, data: { key: value, ... } }
      pipeline_end { final_state }
      error        { message }
    """
    initial_state = {
        "topic": req.topic,
        "search_results": "",
        "scraped_content": "",
        "report": "",
        "feedback": "",
        "revision_num": 0,
        "max_revisions": req.max_revisions,
        "critic_score": 0,
        "score_threshold": req.score_threshold,
        "messages": [],
    }

    merged_state = dict(initial_state)

    try:
        # Import the compiled graph only when we actually run a pipeline.
        from graph import research_graph

        # Stream LangGraph updates as they arrive.
        # Use a background thread to run the synchronous state graph and push
        # updates into an asyncio.Queue so we can yield them to the SSE client
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        def run_graph():
            try:
                for step in research_graph.stream(initial_state, stream_mode="updates"):
                    # marshal step into the async queue from the thread
                    loop.call_soon_threadsafe(q.put_nowait, step)
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, {"__error": str(e)})
            finally:
                # sentinel to indicate completion
                loop.call_soon_threadsafe(q.put_nowait, None)

        # start the blocking graph runner in a thread (do not await it)
        loop.run_in_executor(None, run_graph)

        # consume events as they arrive
        should_skip_search_reader = False
        while True:
            step = await q.get()
            if step is None:
                break
            if isinstance(step, dict) and step.get("__error"):
                raise Exception(step.get("__error"))

            # Check if memory_check indicated a cache hit (which skips search + reader)
            if "memory_check" in step:
                memory_output = step["memory_check"]
                if memory_output.get("memory_hit"):
                    should_skip_search_reader = True
                    merged_state.update(memory_output)
                    # Emit node_start and node_done for memory_check
                    print(f"SSE -> node_start: memory_check")
                    yield {
                        "event": "node_start",
                        "data": json.dumps({"node": "memory_check"}),
                    }
                    await asyncio.sleep(0)
                    safe_output = {
                        k: v for k, v in memory_output.items()
                        if isinstance(v, (str, int, float, bool, type(None)))
                    }
                    print(f"SSE -> node_done: memory_check (cached)")
                    yield {
                        "event": "node_done",
                        "data": json.dumps({"node": "memory_check", "data": safe_output}),
                    }
                    await asyncio.sleep(0)
                    # Emit synthetic skip events for search and reader
                    for skipped_node in ["search", "reader"]:
                        print(f"SSE -> node_skipped: {skipped_node} (cache hit)")
                        yield {
                            "event": "node_done",
                            "data": json.dumps({"node": skipped_node, "data": {"status": "skipped"}}),
                        }
                        await asyncio.sleep(0)
                    continue

            for node_name, node_output in step.items():
                # node_start
                print(f"SSE -> node_start: {node_name}")
                yield {
                    "event": "node_start",
                    "data": json.dumps({"node": node_name}),
                }
                await asyncio.sleep(0)  # yield control

                # merge output into state
                merged_state.update(node_output)

                # strip non-serialisable message objects
                safe_output = {
                    k: v for k, v in node_output.items()
                    if isinstance(v, (str, int, float, bool, type(None)))
                }

                print(f"SSE -> node_done: {node_name} data_keys={list(safe_output.keys())}")
                yield {
                    "event": "node_done",
                    "data": json.dumps({"node": node_name, "data": safe_output}),
                }
                await asyncio.sleep(0)

        # Final state — only JSON-serialisable fields
        final = {
            k: v for k, v in merged_state.items()
            if isinstance(v, (str, int, float, bool, type(None)))
        }
        yield {
            "event": "pipeline_end",
            "data": json.dumps({"final_state": final}),
        }

    except Exception as exc:
        yield {
            "event": "error",
            "data": json.dumps({"message": str(exc)}),
        }


@app.post("/api/research")
async def research(req: ResearchRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
    return EventSourceResponse(pipeline_stream(req))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/sse-test")
async def sse_test():
    async def gen():
        for i in range(1, 6):
            msg = {"count": i, "msg": f"test {i}"}
            print(f"SSE-TEST -> sending {msg}")
            yield {"event": "message", "data": json.dumps(msg)}
            await asyncio.sleep(1)
    return EventSourceResponse(gen())


@app.get("/api/research-stream")
async def research_stream_get(topic: str, max_revisions: int = 3, score_threshold: int = 7):
    # Build a ResearchRequest-like object and stream using the same pipeline_stream
    req = ResearchRequest(topic=topic, max_revisions=max_revisions, score_threshold=score_threshold)
    return EventSourceResponse(pipeline_stream(req))