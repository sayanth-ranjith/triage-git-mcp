"""Core logic for the triage-git-mcp server.

Everything in this package is deliberately MCP-agnostic: it knows about
GitHub, configuration and data shapes, but nothing about tools, hosts or
transports. That boundary lives in `mcp_server.py` at the repo root, which
is the only module that imports the MCP SDK.
"""
