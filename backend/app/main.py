from fastapi import FastAPI

from app.models.base import Base
from app.core.database import engine
from app.api import auth

import app.models
Base.metadata.create_all(bind=engine)


app = FastAPI()

app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "FastAPI is running!"}
