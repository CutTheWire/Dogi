from fastapi import APIRouter, Request, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from domain import ModelRegistry, ErrorTools

llm_router = APIRouter()

@llm_router.get("/models", summary="사용 가능한 AI 모델 목록")
async def get_models():
    """
    사용 가능한 모델 목록
    
    Returns:
        JSONResponse: 모델 ID와 정보 목록
    """
    models = ModelRegistry.list_models()
    return {"models": [model.model_dump() for model in models]}

@llm_router.post("session", summary="새로운 LLM 세션 생성")
async def create_session(request: Request):
    """
    새로운 LLM 세션 생성
    
    Args:
        request (Request): 요청 객체
    
    Returns:
        JSONResponse: 세션 ID와 상태
    """
    return JSONResponse()