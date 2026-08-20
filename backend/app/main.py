from fastapi import FastAPI

app = FastAPI(
    title="Script to Video AI",
    description="AI-powered script-to-video generation workflow",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "Script to Video AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }
