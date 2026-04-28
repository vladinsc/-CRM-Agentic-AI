from fastapi import FastAPI
from routers import agent

app = FastAPI(title="CRM AI Service")


app.include_router(agent.router)


@app.get("/")
def read_root():
    return {"status": "healthy", "message": "AI Service is running"}
