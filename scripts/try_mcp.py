"""Run the MCP server locally and call its tools from the terminal.

Does what a host (Claude Desktop, Copilot) does: launches `mcp_server.py`
as a subprocess, talks MCP to it over stdio, and prints what comes back.

    python scripts/try_mcp.py                      # list tools + your issues
    python scripts/try_mcp.py owner/repo 12        # also fetch one issue's details
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent


def _show(result) -> None:
    if result.is_error:
        print("ERROR:", result.content[0].text)
    else:
        print(json.dumps(result.structured_content, indent=2, default=str))


async def main(repo: str | None, number: int | None) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "mcp_server.py")],
        cwd=str(REPO_ROOT),  # so the server finds .env
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [tool.name for tool in tools.tools])

            print("\n=== list_my_assigned_issues ===")
            _show(await session.call_tool("list_my_assigned_issues", {}))

            if repo:
                print(f"\n=== get_issue_details {repo}#{number} ===")
                _show(
                    await session.call_tool(
                        "get_issue_details", {"repo": repo, "number": number}
                    )
                )


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(args[0] if args else None, int(args[1]) if len(args) > 1 else None))
