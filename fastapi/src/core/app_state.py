from typing import Optional
from llm import Llama
from service import (
    MySQLClient,
    MongoClient,
    VectorClient,
)

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

# 핸들러 인스턴스는 초기에 None으로 설정하고 지연 초기화
mongo_handler: Optional[MongoClient.MongoDBHandler] = None
mysql_handler: Optional[MySQLClient.MySQLDBHandler] = None
llama_model: Optional[Llama.LlamaModel] = None
vector_handler: Optional[VectorClient.VectorSearchHandler] = None

async def initialize_handlers():
    """
    애플리케이션 시작 시 모든 DB 핸들러 및 LLM 모델 초기화
    """
    global mongo_handler, mysql_handler, llama_model, vector_handler

    # Vector DB 핸들러 초기화 (가장 먼저)
    if vector_handler is None:
        try:
            vector_handler = VectorClient.VectorSearchHandler()
            if vector_handler.health_check():
                print(f"{GREEN}INFO{RESET}:     Vector DB 핸들러가 성공적으로 초기화되었습니다.")
            else:
                print(f"{RED}WARNING{RESET}:  Vector DB 연결 실패, RAG 기능이 제한됩니다.")
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
            mysql_handler = MySQLClient.MySQLDBHandler()
            # MySQL 연결
            await mysql_handler.connect()
            print(f"{GREEN}INFO{RESET}:     MySQL 핸들러가 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     MySQL 초기화 오류 발생: {str(e)}")
            mysql_handler = None
    
    # Llama 모델 초기화
    if llama_model is None:
        try:
            llama_model = Llama.LlamaModel()
            print(f"{GREEN}INFO{RESET}:     Llama 모델이 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     Llama 모델 초기화 오류 발생: {str(e)}")
            llama_model = None

async def cleanup_handlers():
    """
    애플리케이션 종료 시 모든 핸들러 정리
    """
    global mysql_handler, mongo_handler

    if mysql_handler:
        await mysql_handler.disconnect()
        print(f"{GREEN}INFO{RESET}:     MySQL 핸들러 연결이 해제되었습니다.")

    if mongo_handler:
        # MongoClient에 close 또는 disconnect 메서드가 있다고 가정
        # mongo_handler.close()
        print(f"{GREEN}INFO{RESET}:     MongoDB 핸들러가 정리되었습니다.")

def get_vector_handler() -> Optional[VectorClient.VectorSearchHandler]:
    """
    Vector DB 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[VectorClient.VectorSearchHandler]: Vector DB 핸들러 인스턴스
    """
    return vector_handler

def get_mongo_handler() -> Optional[MongoClient.MongoDBHandler]:
    """
    MongoDB 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[MongoClient.MongoDBHandler]: MongoDB 핸들러 인스턴스
    """
    return mongo_handler

def get_mysql_handler() -> Optional[MySQLClient.MySQLDBHandler]:
    """
    MySQL 핸들러 인스턴스를 반환하는 함수
    
    Returns:
        Optional[MySQLClient.MySQLDBHandler]: MySQL 핸들러 인스턴스
    """
    return mysql_handler

def get_llama_model() -> Optional[Llama.LlamaModel]:
    """
    Llama 모델 인스턴스를 반환하는 함수
    
    Returns:
        Optional[Llama.LlamaModel]: Llama 모델 인스턴스
    """
    return llama_model
