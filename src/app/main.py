from fastapi import FastAPI
from app.api.routers import flags

app = FastAPI(title="Feature Flag Service")
app.include_router(flags.router)

@app.get("/")
async def root():
    return {"status": "ok"}
