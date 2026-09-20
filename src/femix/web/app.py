from fastapi import FastAPI

app = FastAPI(title="Femix Web Panel")

@app.get("/")
async def root():
    return {"message": "Femix Web Panel"}

@app.get("/health")
async def health():
    return {"status": "ok"}
