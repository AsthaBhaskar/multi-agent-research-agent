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
def build_search_agent():
    """Returns a callable that mimics the old agent interface."""
    class _Agent:
        def invoke(self, payload):
            msg = payload["messages"][0]
            text = msg[1] if isinstance(msg, tuple) else msg.content
            output = _run_tool_agent(search_llm, text)
            return {"messages": [AIMessage(content=output)]}
    return _Agent()


def build_reader_agent():
    class _Agent:
        def invoke(self, payload):
            msg = payload["messages"][0]
            text = msg[1] if isinstance(msg, tuple) else msg.content
            output = _run_tool_agent(reader_llm, text)
            return {"messages": [AIMessage(content=output)]}
    return _Agent()


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
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Sources (list all URLs found in the research)

Be detailed, factual and professional."""),
])

writer_chain = _writer_prompt | llm | StrOutputParser()


# ── Critic Chain ──────────────────────────────────────────────────────────────
_critic_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this EXACT format (do not deviate):

Score: X/10
Strengths:
- ...
- ...
Areas to Improve:
- ...
- ...
One line verdict:
..."""),
])

critic_chain = _critic_prompt | llm | StrOutputParser()