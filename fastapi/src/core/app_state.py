from typing import Optional
from service import (
    MySQLClient,
    MongoClient,
    VectorClient,
    JWTService,
)

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

# 핸들러 인스턴스는 초기에 None으로 설정하고 지연 초기화
vector_handler: Optional[VectorClient.VectorSearchHandler] = None
mongo_handler: Optional[MongoClient.MongoDBHandler] = None
mysql_handler: Optional[MySQLClient.MongoDBHandler] = None
jwt_service: Optional[JWTService.JWTHandler] = None
llama_model: Optional[object] = None

async def initialize_handlers():
    """
    애플리케이션 시작 시 모든 DB 핸들러 및 LLM 모델 초기화
    """
    global vector_handler, mongo_handler, mysql_handler, jwt_service, llama_model
    
    # Vector DB 핸들러 초기화
    if vector_handler is None:
        try:
            vector_handler = VectorClient.VectorSearchHandler()
            print(f"{GREEN}INFO{RESET}:     Vector DB 핸들러가 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     Vector DB 초기화 오류 발생: {str(e)}")
            vector_handler = None
    
    # MongoDB 핸들러 초기화
    if mongo_handler is None:
        try:
            mongo_handler = MongoClient.MongoDBHandler()
            print(f"{GREEN}INFO{RESET}:     MongoDB 핸들러가 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     MongoDB 초기화 오류 발생: {str(e)}")
            mongo_handler = None
    
    # MySQL 핸들러 초기화
    if mysql_handler is None:
        try:
            mysql_handler = MySQLClient.MongoDBHandler()
            print(f"{GREEN}INFO{RESET}:     MySQL 핸들러가 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     MySQL 초기화 오류 발생: {str(e)}")
            mysql_handler = None
    
    # JWT 서비스 초기화
    if jwt_service is None:
        try:
            jwt_service = JWTService.JWTHandler()
            print(f"{GREEN}INFO{RESET}:     JWT 서비스가 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     JWT 서비스 초기화 오류 발생: {str(e)}")
            jwt_service = None
    
    # Llama 모델 초기화
    if llama_model is None:
        try:
            from llm import Llama
            llama_model = Llama.LlamaModel()
            print(f"{GREEN}INFO{RESET}:     Llama 모델이 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     Llama 모델 초기화 오류 발생: {str(e)}")
            llama_model = None

async def cleanup_handlers():
    """
    애플리케이션 종료 시 모든 DB 핸들러 및 LLM 모델 정리
    """
    global vector_handler, mongo_handler, mysql_handler, jwt_service, llama_model
    
    # Vector DB 핸들러 정리
    if vector_handler is not None:
        try:
            # VectorClient에 cleanup 메서드가 있다면 호출
            if hasattr(vector_handler, 'cleanup'):
                vector_handler.cleanup()
            vector_handler = None
            print(f"{GREEN}INFO{RESET}:     Vector DB 핸들러가 정리되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     Vector DB 정리 중 오류: {str(e)}")
    
    # MongoDB 핸들러 정리
    if mongo_handler is not None:
        try:
            # MongoDB 클라이언트 종료
            if hasattr(mongo_handler, 'client'):
                mongo_handler.client.close()
            mongo_handler = None
            print(f"{GREEN}INFO{RESET}:     MongoDB 핸들러가 정리되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     MongoDB 정리 중 오류: {str(e)}")
    
    # MySQL 핸들러 정리
    if mysql_handler is not None:
        try:
            # MySQL 클라이언트 종료
            if hasattr(mysql_handler, 'close'):
                mysql_handler.close()
            mysql_handler = None
            print(f"{GREEN}INFO{RESET}:     MySQL 핸들러가 정리되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     MySQL 정리 중 오류: {str(e)}")
    
    # JWT 서비스 정리
    if jwt_service is not None:
        try:
            jwt_service = None
            print(f"{GREEN}INFO{RESET}:     JWT 서비스가 정리되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     JWT 서비스 정리 중 오류: {str(e)}")
    
    # Llama 모델 정리
    if llama_model is not None:
        try:
            # 모델 메모리 정리
            llama_model = None
            print(f"{GREEN}INFO{RESET}:     Llama 모델이 정리되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     Llama 모델 정리 중 오류: {str(e)}")

def get_vector_handler() -> Optional[VectorClient.VectorSearchHandler]:
    """
    Vector DB 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[VectorClient.VectorSearchHandler]: 벡터 검색 클라이언트 인스턴스
    """
    return vector_handler

def get_mongo_handler() -> Optional[MongoClient.MongoDBHandler]:
    """
    MongoDB 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[MongoClient.MongoDBHandler]: MongoDB 핸들러 인스턴스
    """
    return mongo_handler

def get_mysql_handler() -> Optional[MySQLClient.MongoDBHandler]:
    """
    MySQL 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[MySQLClient.MySQLClient]: MySQL 핸들러 인스턴스
    """
    return mysql_handler

def get_jwt_service() -> Optional[JWTService.JWTHandler]:
    """
    JWT 서비스 인스턴스를 반환하는 함수
    
    Returns:
        Optional[JWTService.JWTHandler]: JWT 서비스 인스턴스
    """
    return jwt_service

def get_llama_model():
    """
    Llama 모델 인스턴스를 반환하는 함수
    
    Returns:
        Optional[LlamaModel]: Llama 모델 인스턴스
    """
    return llama_model
