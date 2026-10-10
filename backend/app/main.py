from fastapi import FastAPI,HTTPException
from fastapi.exceptions import RequestValidationError
from app.models.base import Base
from app.core.database import engine
from app.api import auth, user
from app.core.exceptions import (
     BusinessException,
    bussiness_excpetion_hadler,
    http_excpetion_hadler,
    validation_excpetion_hadler,
    global_excpetion_hadler,
)

import app.models

Base.metadata.create_all(bind=engine)


app = FastAPI()

app.include_router(auth.router)
app.include_router(user.router)


app.add_exception_handler(BusinessException, bussiness_excpetion_hadler)
app.add_exception_handler(HTTPException, http_excpetion_hadler)
app.add_exception_handler(RequestValidationError, validation_excpetion_hadler)
# 全局的异常兜底，必须放在最后注册！！
app.add_exception_handler(Exception, global_excpetion_hadler)

@app.get("/")
def root():
    return {"message": "FastAPI is running!"}
