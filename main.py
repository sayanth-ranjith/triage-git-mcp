from fastapi import FastAPI

app = FastAPI(title="triage-git-mcp")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
