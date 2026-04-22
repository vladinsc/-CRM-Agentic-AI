from http.client import HTTPException

from fastapi import FastAPI
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, messages 


app = FastAPI(title="CRM Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(messages.router)
@app.get("/")
def read_root():
    return {"status": "healthy", "message": "Service is running"}


