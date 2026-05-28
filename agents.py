"""
LLM chains and tool-calling agents compatible with older langgraph versions.
No create_react_agent needed — uses LangChain's bind_tools + manual tool dispatch.
"""
import json
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from tools import web_search, scrape_url
from dotenv import load_dotenv

load_dotenv()

# ── Shared LLM ────────────────────────────────────────────────────────────────
llm = ChatMistralAI(model="mistral-small-latest", temperature=0)

# LLMs with tools bound (for tool-calling)
search_llm = llm.bind_tools([web_search])
reader_llm = llm.bind_tools([scrape_url])

TOOLS = {
    "web_search": web_search,
    "scrape_url": scrape_url,
}


def _run_tool_agent(bound_llm, user_message: str, max_steps: int = 5) -> str:
    """
    Simple agentic loop:
      1. Send messages to LLM
      2. If it calls a tool → execute it, append result, loop
      3. If it returns plain text → done
    Works with any langgraph/langchain version.
    """
    messages = [HumanMessage(content=user_message)]

    for _ in range(max_steps):
        response = bound_llm.invoke(messages)
        messages.append(response)

        # No tool calls → final answer
        if not getattr(response, "tool_calls", None):
            return response.content

        # Execute every tool call
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_fn   = TOOLS.get(tool_name)

            if tool_fn:
                try:
                    # LangChain @tool functions accept kwargs
                    result = tool_fn.invoke(tool_args)
                except Exception as e:
                    result = f"Tool error: {e}"
            else:
                result = f"Unknown tool: {tool_name}"

            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))

    # Fallback: return last AI message content
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            return m.content
    return "Agent did not produce a final answer."


# ── Public agent builders ─────────────────────────────────────────────────────
class _ToolAgent:
    def __init__(self, bound_llm):
        self._llm = bound_llm

    def invoke(self, payload):
        msg = payload["messages"][0]
        text = msg[1] if isinstance(msg, tuple) else msg.content
        output = _run_tool_agent(self._llm, text)
        return {"messages": [AIMessage(content=output)]}

_search_agent = _ToolAgent(search_llm)
_reader_agent = _ToolAgent(reader_llm)

def build_search_agent():
    return _search_agent

def build_reader_agent():
    return _reader_agent

# ── Writer Chain ──────────────────────────────────────────────────────────────
_writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

{revision_instruction}

Structure the report as:
- Introduction
- Key Findings (minimum 3 points — each must include a named source inline, \
a specific statistic or example, and at least one industry-specific detail)
- Regulatory & Ethical Landscape (name at least one real framework, e.g. EU AI Act)
- Conclusion
- Sources (list all URLs found in the research)

If you are uncertain about a statistic, write "reportedly" or "according to [source]" \
rather than stating it as fact. Do not invent numbers.
     
CRITICAL RULES:
- Only cite URLs that appear verbatim in the Research Gathered section above.
- Do not invent, guess, or paraphrase URLs. If a URL is not in the research, do not include it.
- If a claim cannot be attributed to a URL in the research, write "based on available research" — do not fabricate a source.
- For every statistic or named claim, write the source inline, e.g. (Source: https://...)
"""),
])

writer_chain = _writer_prompt | llm | StrOutputParser()


# ── Critic Chain ──────────────────────────────────────────────────────────────
_critic_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific. Always respond in plain text with no HTML, no markdown bold, no special formatting — only the exact format requested."),
    ("human", """Review the research report below and evaluate it strictly.

Example of the EXACT format you must use:
---
Score: 6/10
Strengths:
- Clear structure across sections.
Areas to Improve:
- No inline source citations in Key Findings.
- Workforce section lacks industry-specific data.
One-line Verdict: Solid overview but needs deeper sourcing.
---

Now review this report:

Report:
{report}

Respond in the EXACT format shown above. Do not add extra sections."""),
])

critic_chain = _critic_prompt | llm | StrOutputParser()