from fastapi import HTTPException, status
from typing import Optional

from . import app_state
from llm import Llama
from service import (
    MySQLClient,
    MongoClient,
    JWTService,
    VectorClient
)

async def get_mongo_client() -> MongoClient.MongoDBHandler:
    """
    FastAPI 의존성 주입을 통해 MongoDB 클라이언트를 가져옵니다.
    
    Returns:
        MongoClient.MongoDBHandler: MongoDB 핸들러 인스턴스.
    """
    handler = app_state.get_mongo_handler()
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB 서비스를 사용할 수 없습니다."
        )
    return handler

async def get_mysql_client() -> MySQLClient.MongoDBHandler:
    """
    FastAPI 의존성 주입을 통해 MySQL 클라이언트를 가져옵니다.
    
    Returns:
        MySQLClient.MySQLClient: MySQL 핸들러 인스턴스.
    """
    handler = app_state.get_mysql_handler()
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MySQL 서비스를 사용할 수 없습니다."
        )
    return handler

async def get_llama_model() -> Llama.LlamaModel:
    """
    FastAPI 의존성 주입을 통해 Llama 모델을 가져옵니다.
    
    Returns:
        LlamaModel: Llama 모델 인스턴스.
    """
    model = app_state.get_llama_model()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM 서비스를 사용할 수 없습니다."
        )
    return model

async def get_jwt_service() -> JWTService.JWTHandler:
    """
    FastAPI 의존성 주입을 통해 JWT 서비스를 가져옵니다.
    
    Returns:
        JWTService.JWTHandler: JWT 서비스 인스턴스.
    """
    handler = app_state.get_jwt_service()
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT 서비스를 사용할 수 없습니다."
        )
    return handler

async def get_current_user_id(authorization: Optional[str] = None) -> str:
    """
    Authorization 헤더에서 사용자 ID를 추출합니다.
    JWT 토큰을 파싱해서 사용자 ID를 반환합니다.
    
    Args:
        authorization: Authorization 헤더 값
        
    Returns:
        str: 사용자 ID
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다."
        )
    
    jwt_service = app_state.get_jwt_service()
    if jwt_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT 서비스를 사용할 수 없습니다."
        )
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt_service.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰입니다."
            )
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다."
        )

def get_vector_client() -> VectorClient.VectorSearchHandler:
    """
    VectorSearchHandler 의존성 주입
    """
    handler = app_state.get_vector_handler()
    if handler is None:
        raise HTTPException(
            status_code=503,
            detail="Vector DB 서비스를 사용할 수 없습니다."
        )
    return handler