"""Ask the MCP server questions in plain English, with Claude as the host.

This is a minimal MCP *host*, the same role Copilot or Claude Code plays:

1. Launch `mcp_server.py` as a subprocess and connect to it over stdio.
2. Ask the server which tools it has (`tools/list`) and describe them to
   Claude.
3. Send your question to Claude. When Claude asks for a tool, run it on the
   MCP server (`tools/call`) and hand the result back. Repeat until Claude
   answers in words.

    python scripts/ask.py                          # interactive chat
    python scripts/ask.py "what's on my plate?"    # one question, then exit
    python scripts/ask.py -v "tell me about #12"   # also print raw tool results

Needs ANTHROPIC_API_KEY (in the environment or `.env`) as well as the
GITHUB_TOKEN the server itself needs. Every question is a paid Claude API
call.

The loop is written out by hand rather than using the SDK's tool runner, so
each step a host performs is a line you can put a breakpoint on.
"""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool

REPO_ROOT = Path(__file__).resolve().parent.parent

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
# Triage chat is light reasoning; "low" keeps answers quick and cheap.
# Raise to "medium" (this model's default) or "high" if answers feel shallow.
EFFORT = "low"
# If a safety classifier declines a request, the API retries it on a
# suitable fallback model inside the same call instead of just stopping.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = f"""\
You help the user triage the GitHub issues assigned to them, using the tools
provided. Today is {date.today().isoformat()}. Keep answers short and lead
with what to work on next."""


def to_claude_tool(tool: Tool) -> dict[str, Any]:
    """MCP and the Claude API describe a tool the same way, under different keys."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema,
    }


def result_text(result: CallToolResult) -> str:
    # The server also sends its structured output as JSON text (one block
    # per issue for a list), so the text blocks carry everything. On an
    # error they carry the message instead.
    return "\n".join(block.text for block in result.content if block.type == "text")


async def run_tool(session: ClientSession, call: Any, *, verbose: bool) -> dict[str, Any]:
    """Run one tool call from Claude on the MCP server; return it as a tool_result."""
    print(f"  -> {call.name}({json.dumps(call.input)})")
    result = await session.call_tool(call.name, call.input)
    text = result_text(result)

    if result.is_error:
        print(f"  <- error: {text}")
    else:
        print(f"  <- {len(text)} characters of JSON")
    if verbose:
        print(text)

    # is_error tells Claude the call failed, so it can fix its arguments
    # and try again rather than treating the message as data.
    return {
        "type": "tool_result",
        "tool_use_id": call.id,  # must match the tool_use block it answers
        "content": text,
        "is_error": bool(result.is_error),
    }


async def answer(
    claude: anthropic.AsyncAnthropic,
    session: ClientSession,
    tools: list[dict[str, Any]],
    messages: list[Any],
    *,
    verbose: bool,
) -> str:
    """Run the tool-use loop for the latest question and return Claude's answer.

    `messages` is the whole conversation and only ever grows, so follow-ups
    like "tell me more about the second one" have context.
    """
    while True:
        response = await claude.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            output_config={"effort": EFFORT},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        # Keep every block, not just the text: tool_use blocks must be
        # there for the tool_results to refer to, and thinking blocks must
        # be sent back unchanged.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "(Claude declined to answer this one.)"
        if response.stop_reason == "max_tokens":
            return "(The answer hit the max_tokens limit and was cut off.)"

        tool_calls = [block for block in response.content if block.type == "tool_use"]
        if not tool_calls:
            return "\n".join(block.text for block in response.content if block.type == "text")

        # All results go back in one user message; splitting them across
        # messages teaches Claude to stop making parallel calls.
        results = [await run_tool(session, call, verbose=verbose) for call in tool_calls]
        messages.append({"role": "user", "content": results})


async def main(question: str | None, verbose: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")  # ANTHROPIC_API_KEY may live there
    claude = anthropic.AsyncAnthropic()
    # Checked before connecting: the SDK only notices missing credentials
    # when the first request is built, mid-conversation.
    if not (claude.api_key or claude.auth_token or claude.credentials):
        sys.exit("No Anthropic credentials found. Put ANTHROPIC_API_KEY=... in .env.")

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "mcp_server.py")],
        cwd=str(REPO_ROOT),  # so the server finds .env
    )
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = await session.list_tools()
        tools = [to_claude_tool(tool) for tool in listed.tools]
        print(f"Connected. Tools: {', '.join(tool['name'] for tool in tools)}")

        messages: list[Any] = []
        while True:
            if question is None:
                try:
                    text = (await asyncio.to_thread(input, "\nyou> ")).strip()
                except (EOFError, KeyboardInterrupt):
                    return
                if text.lower() in {"", "exit", "quit"}:
                    return
            else:
                text = question

            messages.append({"role": "user", "content": text})
            try:
                reply = await answer(claude, session, tools, messages, verbose=verbose)
            except anthropic.AuthenticationError:
                # Return rather than exit, so the MCP connection closes cleanly.
                print("Anthropic rejected the credentials. Check ANTHROPIC_API_KEY in .env.")
                return
            print(f"\nclaude> {reply}")

            if question is not None:
                return


if __name__ == "__main__":
    # Windows consoles default to cp1252, which can't print every character
    # Claude or GitHub may send.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question", nargs="?", help="ask once and exit; omit for a chat")
    parser.add_argument("-v", "--verbose", action="store_true", help="print raw tool results")
    args = parser.parse_args()
    asyncio.run(main(args.question, args.verbose))
