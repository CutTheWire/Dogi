from fastapi import HTTPException, status, Depends
from typing import Optional

from . import app_state
from llm import Llama
from service import (
    MySQLClient,
    MongoClient,
    VectorClient
)

async def get_mongo_client() -> MongoClient.MongoDBHandler:
    """
    MongoDB 핸들러 의존성 주입
    """
    mongo_handler = app_state.get_mongo_handler()
    if mongo_handler is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB 서비스를 사용할 수 없습니다."
        )
    return mongo_handler

async def get_mysql_client() -> MySQLClient.MySQLDBHandler:
    """
    MySQL 핸들러 의존성 주입
    """
    mysql_handler = app_state.get_mysql_handler()
    if mysql_handler is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL 서비스를 사용할 수 없습니다."
        )
    return mysql_handler

async def get_llama_model() -> Llama.LlamaModel:
    """
    Llama 모델 의존성 주입
    """
    llama_model = app_state.get_llama_model()
    if llama_model is None:
        raise HTTPException(
            status_code=503,
            detail="Llama 모델 서비스를 사용할 수 없습니다."
        )
    return llama_model

async def get_vector_client() -> VectorClient.VectorSearchHandler:
    """
    Vector 클라이언트 의존성 주입
    """
    vector_handler = app_state.get_vector_handler()
    if vector_handler is None:
        raise HTTPException(
            status_code=503,
            detail="Vector 서비스를 사용할 수 없습니다."
        )
    return vector_handler