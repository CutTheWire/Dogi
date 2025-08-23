from fastapi import APIRouter, Request, Depends, Path, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from typing import Optional
import json
import asyncio

from core import Dependencies
from llm import Llama
from service import (
    MongoClient,
    JWTService
)
from domain import (
    ModelRegistry,
    ErrorTools,
    Schema,
)

llm_router = APIRouter()

def get_current_user_id(authorization: str = Header(..., description="Bearer JWT 토큰")) -> str:
    """
    Authorization 헤더에서 JWT 토큰을 추출하고 사용자 ID를 반환합니다.
    
    Args:
        authorization: "Bearer {jwt_token}" 형식의 Authorization 헤더
    
    Returns:
        str: JWT 토큰에서 추출한 user_id
    
    Raises:
        HTTPException: 토큰이 유효하지 않거나 user_id를 추출할 수 없는 경우
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        token = authorization.replace("Bearer ", "")
        
        # JWT 서비스 직접 인스턴스 생성
        jwt_service = JWTService.JWTHandler()
        
        # JWT 토큰에서 사용자 ID 추출
        user_id = jwt_service.extract_user_id(token)
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in token"
            )
        
        return user_id
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token validation failed: {str(e)}"
        )

@llm_router.get("/models", summary="사용 가능한 AI 모델 목록")
async def get_models():
    """
    사용 가능한 AI 모델 목록을 조회합니다.
    
    Returns:
        JSONResponse: 모델 ID와 정보 목록
    """
    models = ModelRegistry.list_models()
    return {"models": [model.model_dump() for model in models]}

@llm_router.post("/sessions", summary="새로운 LLM 세션 생성", status_code=201)
async def create_session(
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    새로운 LLM 세션을 생성합니다.
    
    Args:
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 생성된 세션 ID
    """
    try:
        session_id = await mongo_handler.create_llm_session(current_user_id)
        return JSONResponse(
            content={"session_id": session_id},
            status_code=201
        )
    except ValidationError as e:
        raise ErrorTools.ValueErrorException(
            status_code=422,
            detail="세션 생성에 실패했습니다.",
            errors=e.errors()
        )

@llm_router.get("/sessions", summary="LLM 세션 목록 조회")
async def get_sessions(
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    사용자의 LLM 세션 목록을 조회합니다.
    
    Args:
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 세션 목록
    """
    try:
        sessions = await mongo_handler.get_llm_sessions(current_user_id)
        return {"sessions": sessions}
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 목록 조회 중 오류: {str(e)}")

@llm_router.get("/sessions/{session_id}", summary="LLM 세션 입장")
async def get_session(
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    특정 LLM 세션에 입장합니다.
    
    Args:
        session_id: 세션 ID
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 세션 정보
    """
    try:
        session = await mongo_handler.get_llm_session(current_user_id, session_id)
        return session
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 조회 중 오류: {str(e)}")

@llm_router.delete("/sessions/{session_id}", summary="LLM 세션 삭제", status_code=204)
async def delete_session(
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    특정 LLM 세션을 삭제합니다.
    
    Args:
        session_id: 세션 ID
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 삭제 완료 메시지
    """
    try:
        message = await mongo_handler.delete_llm_session(current_user_id, session_id)
        return JSONResponse(
            content={"message": "세션이 성공적으로 삭제되었습니다."},
            status_code=204
        )
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 삭제 중 오류: {str(e)}")

@llm_router.post("/sessions/{session_id}/messages", summary="LLM 세션에 메시지 추가")
async def add_message(
    request: Schema.MessageRequest,
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client),
    llama_model: Llama.LlamaModel = Depends(Dependencies.get_llama_model)
):
    """
    LLM 세션에 새로운 메시지를 추가합니다. (스트리밍 응답)
    """
    async def stream_response():
        try:
            # 기존 대화 목록 가져오기
            chat_list = await mongo_handler.get_llm_messages(current_user_id, session_id)
            
            answer_chunks = []
            
            # 스트리밍으로 응답 생성 및 전송
            for chunk in llama_model.generate_response_stream(
                input_text=request.content,
                chat_list=chat_list
            ):
                answer_chunks.append(chunk)
                yield chunk
            
            # 전체 응답 완성 후 MongoDB에 저장
            full_answer = "".join(answer_chunks)
            await mongo_handler.add_llm_message(
                user_id=current_user_id,
                session_id=session_id,
                content=request.content,
                model_id=request.model_id,
                answer=full_answer
            )
            
        except Exception as e:
            yield f"[ERROR] 메시지 추가 중 오류: {str(e)}"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@llm_router.get("/sessions/{session_id}/messages", summary="LLM 세션 메시지 목록 조회")
async def get_messages(
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    특정 LLM 세션의 메시지 목록을 조회합니다.
    
    Args:
        session_id: 세션 ID
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 메시지 목록
    """
    try:
        messages = await mongo_handler.get_llm_messages(current_user_id, session_id)
        
        # 날짜 형식을 ISO 문자열로 변환
        formatted_messages = []
        for message in messages:
            formatted_message = {
                "message_idx": message["message_idx"],
                "content": message["content"],
                "answer": message["answer"],
                "created_at": message["created_at"].isoformat() if message.get("created_at") else None,
                "updated_at": message["updated_at"].isoformat() if message.get("updated_at") else None
            }
            formatted_messages.append(formatted_message)
        
        return {"messages": formatted_messages}
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"메시지 조회 중 오류: {str(e)}")

@llm_router.patch("/sessions/{session_id}/messages", summary="LLM 세션 마지막 대화 수정")
async def update_last_message(
    request: Schema.MessageUpdateRequest,
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client),
    llama_model: Llama.LlamaModel = Depends(Dependencies.get_llama_model)
):
    """
    LLM 세션의 마지막 메시지를 수정합니다. (스트리밍 응답)
    """
    async def stream_response():
        try:
            # 기존 대화 목록 가져오기 (마지막 메시지 제외)
            chat_list = await mongo_handler.get_llm_messages(current_user_id, session_id)
            if chat_list:
                chat_list = chat_list[:-1]
            
            answer_chunks = []
            
            # 스트리밍으로 응답 생성 및 전송
            for chunk in llama_model.generate_response_stream(
                input_text=request.content,
                chat_list=chat_list
            ):
                answer_chunks.append(chunk)
                yield chunk
            
            # 전체 응답 완성 후 MongoDB에서 마지막 메시지 수정
            full_answer = "".join(answer_chunks)
            await mongo_handler.update_last_llm_message(
                user_id=current_user_id,
                session_id=session_id,
                content=request.content,
                model_id=request.model_id,
                answer=full_answer
            )
            
        except Exception as e:
            yield f"[ERROR] 메시지 수정 중 오류: {str(e)}"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@llm_router.delete("/sessions/{session_id}/messages", summary="LLM 세션 마지막 대화 삭제", status_code=204)
async def delete_last_message(
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client)
):
    """
    LLM 세션의 마지막 메시지를 삭제합니다.
    
    Args:
        session_id: 세션 ID
        current_user_id: JWT 토큰에서 추출한 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 삭제 완료 메시지
    """
    try:
        message = await mongo_handler.delete_last_llm_message(current_user_id, session_id)
        return JSONResponse(
            content={"message": "마지막 메시지가 성공적으로 삭제되었습니다."},
            status_code=204
        )
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"메시지 삭제 중 오류: {str(e)}")

@llm_router.post("/sessions/{session_id}/regenerate", summary="LLM 세션 마지막 메시지 재생성")
async def regenerate_last_message(
    request: Schema.RegenerateRequest,
    session_id: str = Path(..., description="세션 ID"),
    current_user_id: str = Depends(get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(Dependencies.get_mongo_client),
    llama_model: Llama.LlamaModel = Depends(Dependencies.get_llama_model)
):
    """
    LLM 세션의 마지막 메시지를 재생성합니다. (스트리밍 응답)
    """
    async def stream_response():
        try:
            # 기존 대화 목록 가져오기
            chat_list = await mongo_handler.get_llm_messages(current_user_id, session_id)
            if not chat_list:
                yield "[ERROR] 재생성할 메시지가 없습니다."
                return
            
            # 마지막 메시지의 content 가져오기
            last_message = chat_list[-1]
            content = last_message["content"]
            
            # 마지막 메시지 제외한 대화 목록
            chat_list = chat_list[:-1]
            
            answer_chunks = []
            
            # 스트리밍으로 응답 생성 및 전송
            for chunk in llama_model.generate_response_stream(
                input_text=content,
                chat_list=chat_list
            ):
                answer_chunks.append(chunk)
                yield chunk
            
            # 전체 응답 완성 후 MongoDB에서 마지막 메시지 재생성
            full_answer = "".join(answer_chunks)
            await mongo_handler.regenerate_last_llm_message(
                user_id=current_user_id,
                session_id=session_id,
                model_id=request.model_id,
                answer=full_answer
            )
            
        except Exception as e:
            yield f"[ERROR] 메시지 재생성 중 오류: {str(e)}"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

