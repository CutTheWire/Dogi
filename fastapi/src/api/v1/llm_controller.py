from fastapi import APIRouter, Request, Depends, Path, Header
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Optional

from core import dependencies
from llm import Llama
from service import (
    MongoClient,
    VectorClient,
)
from domain import (
    ModelRegistry,
    ErrorTools,
    Schema,
)

async def _get_vector_search_context(vector_handler, query: str) -> str:
    """
    벡터 검색을 통해 관련 컨텍스트를 가져오는 헬퍼 함수
    
    Args:
        vector_handler: 벡터 검색 핸들러
        query: 검색 쿼리
    
    Returns:
        str: 검색된 컨텍스트
    """
    search_context = ""
    if vector_handler:
        try:
            print(f"    🔍 벡터 검색 시작: '{query[:50]}...'")
            search_context = vector_handler.get_context_for_llm(
                query=query,
                max_context_length=2000
            )
            print(f"    ✅ 벡터 검색 완료: {len(search_context)} 문자")
        except Exception as e:
            print(f"    ⚠️ 벡터 검색 오류 (무시됨): {e}")
    else:
        print(f"    ⚠️ 벡터 검색 핸들러 없음")
    
    return search_context

llm_router = APIRouter()

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
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    새로운 LLM 세션을 생성합니다.
    
    Args:
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 생성된 세션 ID
    """
    try:
        session_id = await mongo_handler.create_llm_session(user_id)
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
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    사용자의 LLM 세션 목록을 조회합니다.
    
    Args:
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 세션 목록
    """
    try:
        sessions = await mongo_handler.get_llm_sessions(user_id)
        return {"sessions": sessions}
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 목록 조회 중 오류: {str(e)}")

@llm_router.get("/sessions/{session_id}", summary="LLM 세션 입장")
async def get_session(
    session_id: str = Path(..., description="세션 ID"),
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    특정 LLM 세션에 입장합니다.
    
    Args:
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 세션 정보
    """
    try:
        session = await mongo_handler.get_llm_session(user_id, session_id)
        return session
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 조회 중 오류: {str(e)}")

@llm_router.delete("/sessions/{session_id}", summary="LLM 세션 삭제", status_code=204)
async def delete_session(
    session_id: str = Path(..., description="세션 ID"),
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    특정 LLM 세션을 삭제합니다.
    
    Args:
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 삭제 완료 메시지
    """
    try:
        message = await mongo_handler.delete_llm_session(user_id, session_id)
        return JSONResponse(
            content={"message": "세션이 성공적으로 삭제되었습니다."},
            status_code=204
        )
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"세션 삭제 중 오류: {str(e)}")

@llm_router.post("/sessions/{session_id}/messages", summary="LLM 세션에 메시지 추가", status_code=201)
async def add_message(
    request: Schema.MessageRequest,
    session_id: str = Path(..., description="세션 ID"),
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client),
    vector_handler: VectorClient.VectorSearchHandler = Depends(dependencies.get_vector_client),
    llama_model: Llama.LlamaModel = Depends(dependencies.get_llama_model)
):
    """
    LLM 세션에 새로운 메시지를 추가합니다.
    
    Args:
        request: 메시지 요청 데이터
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
        vector_handler: 벡터 검색 핸들러
        llama_model: Llama 모델
    
    Returns:
        JSONResponse: 추가된 메시지 정보
    """
    try:
        # 기존 대화 목록 가져오기
        chat_list = await mongo_handler.get_llm_messages(user_id, session_id)
        
        # 벡터 검색으로 관련 정보 가져오기
        search_context = await _get_vector_search_context(vector_handler, request.content)
        
        # Llama 모델로 응답 생성
        answer = llama_model.generate_response(
            input_text=request.content,
            search_text=search_context,
            chat_list=chat_list
        )
        
        # MongoDB에 메시지 저장
        message = await mongo_handler.add_llm_message(
            user_id=user_id,
            session_id=session_id,
            content=request.content,
            model_id=request.model_id,
            answer=answer
        )
        
        return JSONResponse(
            content={
                "message_idx": message["message_idx"],
                "answer": message["answer"],
                "created_at": message["created_at"].isoformat(),
                "updated_at": message["updated_at"].isoformat()
            },
            status_code=201
        )
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"메시지 추가 중 오류: {str(e)}")

@llm_router.get("/sessions/{session_id}/messages", summary="LLM 세션 메시지 목록 조회")
async def get_messages(
    session_id: str = Path(..., description="세션 ID"),
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    특정 LLM 세션의 메시지 목록을 조회합니다.
    
    Args:
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 메시지 목록
    """
    try:
        messages = await mongo_handler.get_llm_messages(user_id, session_id)
        
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
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client),
    vector_handler: VectorClient.VectorSearchHandler = Depends(dependencies.get_vector_client),
    llama_model: Llama.LlamaModel = Depends(dependencies.get_llama_model)
):
    """
    LLM 세션의 마지막 메시지를 수정합니다.
    
    Args:
        request: 메시지 수정 요청 데이터
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
        vector_handler: 벡터 검색 핸들러
        llama_model: Llama 모델
    
    Returns:
        JSONResponse: 수정된 메시지 정보
    """
    try:
        # 기존 대화 목록 가져오기 (마지막 메시지 제외)
        chat_list = await mongo_handler.get_llm_messages(user_id, session_id)
        if chat_list:
            chat_list = chat_list[:-1]  # 마지막 메시지 제외
        
        # 벡터 검색으로 관련 정보 가져오기
        search_context = await _get_vector_search_context(vector_handler, request.content)
        
        # Llama 모델로 새로운 응답 생성
        answer = llama_model.generate_response(
            input_text=request.content,
            search_text=search_context,
            chat_list=chat_list
        )
        
        # MongoDB에서 마지막 메시지 수정
        message = await mongo_handler.update_last_llm_message(
            user_id=user_id,
            session_id=session_id,
            content=request.content,
            model_id=request.model_id,
            answer=answer
        )
        
        return {
            "message_idx": message["message_idx"],
            "answer": message["answer"],
            "created_at": message["created_at"].isoformat(),
            "updated_at": message["updated_at"].isoformat()
        }
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"메시지 수정 중 오류: {str(e)}")

@llm_router.delete("/sessions/{session_id}/messages", summary="LLM 세션 마지막 대화 삭제", status_code=204)
async def delete_last_message(
    session_id: str = Path(..., description="세션 ID"),
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client)
):
    """
    LLM 세션의 마지막 메시지를 삭제합니다.
    
    Args:
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
    
    Returns:
        JSONResponse: 삭제 완료 메시지
    """
    try:
        message = await mongo_handler.delete_last_llm_message(user_id, session_id)
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
    user_id: str = Depends(dependencies.get_current_user_id),
    mongo_handler: MongoClient.MongoDBHandler = Depends(dependencies.get_mongo_client),
    vector_handler: VectorClient.VectorSearchHandler = Depends(dependencies.get_vector_client),
    llama_model: Llama.LlamaModel = Depends(dependencies.get_llama_model)
):
    """
    LLM 세션의 마지막 메시지를 재생성합니다.
    
    Args:
        request: 재생성 요청 데이터
        session_id: 세션 ID
        user_id: 현재 사용자 ID
        mongo_handler: MongoDB 핸들러
        vector_handler: 벡터 검색 핸들러
        llama_model: Llama 모델
    
    Returns:
        JSONResponse: 재생성된 메시지 정보
    """
    try:
        # 기존 대화 목록 가져오기
        chat_list = await mongo_handler.get_llm_messages(user_id, session_id)
        if not chat_list:
            raise ErrorTools.NotFoundException("재생성할 메시지가 없습니다.")
        
        # 마지막 메시지의 content 가져오기
        last_message = chat_list[-1]
        content = last_message["content"]
        
        # 마지막 메시지 제외한 대화 목록
        chat_list = chat_list[:-1]
        
        # 벡터 검색으로 관련 정보 가져오기
        search_context = await _get_vector_search_context(vector_handler, content)
        
        # Llama 모델로 새로운 응답 생성
        answer = llama_model.generate_response(
            input_text=content,
            search_text=search_context,
            chat_list=chat_list
        )
        
        # MongoDB에서 마지막 메시지 재생성
        message = await mongo_handler.regenerate_last_llm_message(
            user_id=user_id,
            session_id=session_id,
            model_id=request.model_id,
            answer=answer
        )
        
        return {
            "message_idx": message["message_idx"],
            "answer": message["answer"],
            "created_at": message["created_at"].isoformat(),
            "updated_at": message["updated_at"].isoformat()
        }
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"메시지 재생성 중 오류: {str(e)}")

