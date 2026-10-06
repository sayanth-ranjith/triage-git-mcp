# Where we are, and what iteration 3 changes

A plain-language walkthrough of what the MCP server does **today** and what
we're proposing for the **next iteration** (iteration 3, "enrich issue
context"), written before any code changes. Detailed plan lives in
[`plan/03-enrich-issue-context.md`](plan/03-enrich-issue-context.md); this
doc is the "explain it to me first" version.

---

## 1. Are we getting the issues list today?

**Yes — the code path exists and is unit-tested, but it hasn't been verified
against real GitHub yet.**

### What happens when a host calls the tool

```
Host (Claude Desktop / Copilot)
   │  calls tool: list_my_assigned_issues()   (no arguments)
   ▼
mcp_server.py                      ← composition root, MCP lives only here
   │  _github.list_assigned_issues()
   ▼
triage_git_mcp/github_client.py    ← all HTTP + GitHub JSON knowledge
   │  GET https://api.github.com/issues
   │      ?filter=assigned&state=all&per_page=100
   │  Authorization: Bearer <GITHUB_TOKEN from .env>
   ▼
GitHub returns issues AND pull requests (GitHub treats PRs as issues)
   │  drop anything with a "pull_request" key
   ▼
list[AssignedIssue]  →  { title, repo, url, state }
```

### What you get back per issue

| Field   | Example                         |
|---------|---------------------------------|
| `title` | `Crash when token is empty`     |
| `repo`  | `sayanth-ranjith/triage-git-mcp`|
| `url`   | `https://github.com/.../issues/12` |
| `state` | `open` / `closed`               |

That's deliberately all. It answers "*which* issues are mine?" but not
"*what should I work on next?*" — which is the actual point of the project.

### Known limitations right now

| Limitation | Why it's OK for now | Fixed in |
|---|---|---|
| Only titles/links — no body, labels, comments, PRs | Keeps iteration 2 focused on "does auth + fetch work" | **Iteration 3** |
| Returns open **and** closed issues, everywhere | No filters yet | Iteration 4 |
| Only first page (≤100 issues) | Pagination deferred | Iteration 5 |
| Errors (401, rate limit, network) raise loudly | No graceful handling yet | Iteration 5 |
| Needs a classic PAT with `repo` scope | Fastest way to get working | Iteration 5 |

### Still to tick off before calling iteration 2 "Done"

- [ ] Put a real classic PAT in `.env`
- [ ] Call `list_my_assigned_issues` and compare against github.com
- [ ] Ask the host "what issues are assigned to me?" end to end

> Recommendation: do this live check **before** starting iteration 3, so
> any auth/query problem isn't mixed up with the new enrichment code.

---

## 2. What we plan to improve next (iteration 3)

**Goal:** give the host enough context per issue that you could decide what
to work on *from the answer alone*, without opening GitHub.

### New data to pull in

| Data | Where it comes from | Cost |
|---|---|---|
| Description (body) | Already in the `/issues` response — just not mapped | Free |
| Labels | Already in the `/issues` response | Free |
| Assignees, milestone, created/updated dates, comment count | Already in the response | Free |
| Comments | `GET /repos/{owner}/{repo}/issues/{n}/comments` | +1 request per issue |
| Linked PRs (+ open/merged/draft) | Issue timeline (`cross-referenced` events) | +1 request per issue |

The first three rows are cheap wins: the data is already sitting in the
response we fetch today, we just throw it away.

### Proposed design: summary tool + detail tool

Instead of fetching everything for every issue in one call, split it in two:

```
list_my_assigned_issues()          ← enhanced, still ONE GitHub request
   → title, repo, url, state, number,
     labels, updated_at, comment_count,
     body_preview (first ~300 chars)

get_issue_details(repo, number)    ← NEW, called on demand
   → everything above, plus
     full body,
     last N comments (author, date, text),
     linked PRs with status (open / merged / draft / closed)
```

**Why split it:**

- **Request volume.** With 50 assigned issues, "fetch everything" is
  1 + 50 + 50 = ~101 API calls per question. The split keeps the common
  case at 1 call and only spends more on issues the host actually drills
  into.
- **Token budget for the host's model.** Full comment threads for every
  issue would flood the context; summaries let the model triage first,
  then zoom in.
- **This is how the host naturally works anyway:** "what's on my plate?" →
  list; "tell me more about #12" → detail.

### Proposed answers to the open questions in the plan

| Question | Proposal |
|---|---|
| One call or summary + detail? | **Summary + detail** (above). |
| How to cap long comment threads? | Return the **last 10 comments** by default, each truncated to ~1,000 chars, plus `total_comments` so the host knows more exist. |
| Linked PRs: status or just a link? | **Include status** (open / merged / draft / closed). "PR already merged" vs "no PR yet" is exactly the signal that drives priority. |
| REST or GraphQL? | **Stay on REST for now.** The split design keeps request counts low enough. Revisit GraphQL if `get_issue_details` ends up needing 3+ REST calls per issue. |
| Tool or MCP resource for details? | **Tool.** Resources need the host/user to pick them; tools can be called by the model on its own, which is what we want. |

### Code changes this implies (no structural rewrite)

The iteration-2 split (MCP layer vs. GitHub client vs. models) was built for
exactly this, so changes stay localized:

- `models.py` — extend `AssignedIssue`; add `IssueDetail`, `IssueComment`,
  `LinkedPullRequest` models (their docstrings become the schema the host
  sees, so they're written for the model).
- `github_client.py` — map the extra fields in `_to_issue`; add
  `get_issue_details(repo, number)` and small helpers for comments and
  timeline/linked PRs.
- `mcp_server.py` — register one new thin tool, `get_issue_details`.
  Probably also drop the iteration-1 `echo` tool now that real tools exist.
- `tests/` — unit tests for the new mapping rules (body truncation, comment
  cap, PR-status derivation) with stubbed HTTP, same style as today.

### Explicitly **not** in iteration 3

- Filtering by repo / org / label / open-only → iteration 4
- Pagination, retries, rate-limit handling → iteration 5
  (but we'll note request counts, since this is where they start growing)

### "Done" looks like

1. "What's on my plate?" returns issues with labels, last-updated date and a
   short description — enough to rank them.
2. "Tell me more about #N" returns the full body, recent discussion, and
   whether a PR exists and its state.
3. Tests pass, and both answers are checked against github.com.

---

## 3. Decisions to confirm before implementing

1. OK with the **summary + detail** split (vs. one big call)?
2. Default comment cap of **10** — too many / too few?
3. Remove the `echo` tool now?
4. Do the live iteration-2 verification first, or go straight into iteration 3?
