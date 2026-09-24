from fastapi import FastAPI

app = FastAPI(title="triage-git-mcp")


@app.get("/health")
def health():
    return {"status": "ok"}
