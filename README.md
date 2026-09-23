# triage-git-mcp

An MCP (Model Context Protocol) server that connects GitHub Copilot to your GitHub issues — so you can ask "what's on my plate?" and get a real answer, without leaving your editor.

## Why this exists

Checking assigned issues usually means switching to a browser, hunting through filters, and clicking into each one for context. This project aims to close that gap: trigger it from Copilot, and it fetches the issues assigned to you along with the detail you'd normally have to dig for — description, labels, status, and anything else useful for deciding what to work on next.

The goal isn't just a list of titles. It's enough context that Copilot (and you) can actually reason about priority and next steps without a tab switch.

## What it does (planned)

- Fetches issues currently assigned to you across your repos
- Pulls in the detail that matters — description, labels, comments, linked PRs — not just the title
- Exposes this to Copilot as MCP tools, so it can be triggered conversationally
- (Future) Supports scoping to specific repos/orgs, filtering by label or status, etc.

## Status

Early-stage / learning project. Core flow and tool design are still being figured out.

## Tech stack

_TBD_

## Getting started

_Coming soon — setup instructions will go here once the basic flow is working._
