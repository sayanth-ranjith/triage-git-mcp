# Iteration 5: Auth and resilience

## Goal

Replace the "good enough to get started" personal access token from
iteration 2 with something more appropriate if needed, and make the server
handle GitHub API errors, rate limits, and pagination instead of breaking
loudly.

## Why this next

Deliberately deferred until after the core flow (iterations 2–4) works,
because there's no point hardening a request shape that's still changing.
Now that the shape of what we're fetching is settled, it's worth asking
whether a raw PAT is actually the right long-term auth approach, and making
the thing not fall over on a bad API response, an expired token, or a user
with hundreds of assigned issues.

## What we'll build

- Revisit the PAT approach from iteration 2: is it good enough long-term, or
  does this need a GitHub App / OAuth flow instead? (PAT is simplest but
  ties the server to one person's token, expires, and needs manual
  rotation — worth weighing against the extra setup complexity of the
  alternatives.)
- Handle GitHub API rate limiting (backoff/retry, or at least a clear error
  back to the host instead of a crash).
- Handle pagination properly for users with a lot of assigned issues.
- Handle the common failure cases explicitly: expired/invalid token, repo
  the token can't see, network failure.

## Out of scope (for now)

- Anything not related to auth or robustness of the existing tools — no new
  features here, just making the existing ones trustworthy.

## What "done" looks like

The server keeps working under real conditions: rate limits get hit
occasionally, tokens expire, some repos are private and inaccessible — and
instead of crashing, it degrades predictably and says so.

## New concepts we'll hit here

- GitHub's rate limit model (primary + secondary limits) and how to respect
  it.
- MCP error reporting: how a server tells a host "this call failed" in a way
  the host (and the end user) can understand, vs. just throwing.

## Open questions to resolve in this iteration

- PAT vs. GitHub App vs. OAuth — final call, with the reasoning written down
  here once decided.
- Do we cache anything to reduce API calls, or is that premature for a
  single-user local tool?
