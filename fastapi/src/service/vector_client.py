"""
ChromaDB 벡터 검색 클라이언트
RAG(Retrieval-Augmented Generation)를 위한 벡터 검색 기능 제공
"""
from typing import List, Dict, Any, Optional
from chromadb.config import Settings
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import chromadb
import os
import logging.handlers

from domain import ErrorTools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

class VectorDailyRotating(logging.handlers.BaseRotatingHandler):
    def __init__(self, dir_path: str, date_format: str = "%Y%m%d", encoding=None):
        self.dir_path = dir_path
        self.date_format = date_format
        self.current_date = datetime.now().strftime(self.date_format)
        log_file = os.path.join(self.dir_path, f"{self.current_date}_vector.log")
        super().__init__(log_file, 'a', encoding)

    def shouldRollover(self, record):
        return datetime.now().strftime(self.date_format) != self.current_date

    def doRollover(self):
        self.current_date = datetime.now().strftime(self.date_format)
        self.baseFilename = os.path.join(self.dir_path, f"{self.current_date}_vector.log")
        if self.stream:
            self.stream.close()
            self.stream = self._open()

_formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s:\n%(message)s\n',
    datefmt='%Y-%m-%d %H:%M:%S'
)
if not any(isinstance(h, VectorDailyRotating) for h in logger.handlers):
    _vf = VectorDailyRotating(LOG_DIR, encoding='utf-8')
    _vf.setFormatter(_formatter)
    logger.addHandler(_vf)

class VectorSearchHandler:
    """
    ChromaDB를 사용한 벡터 검색 클라이언트
    의료 데이터에서 관련 문서를 검색하여 LLM에게 컨텍스트 제공
    """
    
    def __init__(self) -> None:
        """
        벡터 검색 클라이언트 초기화
        """
        env_file_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(env_file_path)
        
        self.chroma_host = os.getenv('CHROMA_HOST', 'localhost')
        self.chroma_port = os.getenv('CHROMA_PORT', '7999')
        self.collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'vet_medical_data')
        
        self.client = None
        self.collection = None
        self.connection_status = "DISCONNECTED"
        self.available_departments = []
        self.available_source_types = []
        self.last_search_info = {}
        
        try:
            self._connect_to_chroma()
            self._ensure_collection_exists()
            logger.info(f"VectorSearchHandler 초기화 완료")
        except Exception as e:
            logger.error(f"VectorSearchHandler 초기화 실패: {e}")
            self.client = None
            self.collection = None
            self.connection_status = "FAILED"

    def _connect_to_chroma(self):
        """ChromaDB에 연결"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            chroma_url = f"http://{self.chroma_host}:{self.chroma_port}"
            logger.info(f"ChromaDB 연결 시도: {chroma_url}")
            
            self.client = chromadb.HttpClient(
                host=self.chroma_host,
                port=int(self.chroma_port),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 연결 테스트
            self.client.heartbeat()
            self.connection_status = "CONNECTED"
            logger.info(f"ChromaDB 연결 성공: {chroma_url}")
            
        except Exception as e:
            self.connection_status = "DISCONNECTED"
            logger.error(f"ChromaDB 연결 실패: {e}")
            raise

    def _ensure_collection_exists(self):
        """컬렉션이 존재하지 않으면 생성"""
        try:
            # 기존 컬렉션 목록 확인
            collections = self.client.list_collections()
            collection_names = [col.name for col in collections]
            
            if self.collection_name in collection_names:
                # 기존 컬렉션 사용
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"기존 컬렉션 사용: {self.collection_name}")
            else:
                # 새 컬렉션 생성
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "반려동물 의료 데이터 벡터 검색용 컬렉션"}
                )
                logger.info(f"새 컬렉션 생성: {self.collection_name}")
                
                # 샘플 데이터 추가 (빈 컬렉션 방지)
                self._add_sample_data()
            
            # 컬렉션 정보 수집
            self._collect_collection_info()
                
        except Exception as e:
            logger.error(f"컬렉션 설정 실패: {e}")
            raise

    def _collect_collection_info(self):
        """컬렉션 정보 수집"""
        try:
            if self.collection:
                # 샘플 데이터로부터 사용 가능한 옵션 수집
                sample_results = self.collection.get(limit=100)
                
                self.available_departments = []
                self.available_source_types = []
                
                if sample_results['metadatas']:
                    for metadata in sample_results['metadatas']:
                        if metadata.get('department'):
                            dept = metadata['department']
                            if dept not in self.available_departments:
                                self.available_departments.append(dept)
                        
                        if metadata.get('source_type'):
                            source = metadata['source_type']
                            if source not in self.available_source_types:
                                self.available_source_types.append(source)
                
                logger.info(f"사용 가능한 진료과: {self.available_departments}")
                logger.info(f"사용 가능한 데이터 타입: {self.available_source_types}")
                
        except Exception as e:
            logger.warning(f"컬렉션 정보 수집 실패: {e}")
            self.available_departments = []
            self.available_source_types = []

    def get_connection_status(self) -> Dict[str, Any]:
        """
        연결 상태 정보 반환
        
        Returns:
            Dict: 연결 상태 정보
        """
        status_info = {
            "status": self.connection_status,
            "host": self.chroma_host,
            "port": self.chroma_port,
            "collection_name": self.collection_name,
            "is_connected": self.connection_status == "CONNECTED",
            "document_count": 0,
            "available_departments": getattr(self, 'available_departments', []),
            "available_source_types": getattr(self, 'available_source_types', []),
            "last_search": self.last_search_info
        }
        
        if self.collection:
            try:
                status_info["document_count"] = self.collection.count()
            except:
                pass
                
        return status_info

    def search_relevant_documents(
            self, 
            query: str, 
            n_results: int = 5,
            department: Optional[str] = None,
            source_type: Optional[str] = None
        ) -> List[Dict[str, Any]]:
        """
        질의와 관련된 문서들을 검색
        
        Args:
            query: 검색 질의
            n_results: 반환할 결과 수
            department: 진료과 필터링
            source_type: 소스 타입 필터링 ('corpus', 'qa_question', 'qa_answer')
            
        Returns:
            List[Dict]: 관련 문서들과 메타데이터
        """
        search_start_time = datetime.now()
        
        if not self.collection:
            logger.warning("ChromaDB 컬렉션이 없습니다.")
            return []
        
        try:
            # 검색 정보 로깅
            search_params = {
                "query": query[:100] + "..." if len(query) > 100 else query,
                "n_results": n_results,
                "department": department,
                "source_type": source_type,
                "timestamp": search_start_time.isoformat()
            }
            
            print(f"벡터 검색 실행:")
            print(f"- 질의: {search_params['query']}")
            print(f"- 요청 결과 수: {n_results}")
            if department:
                print(f"- 진료과 필터: {department}")
            if source_type:
                print(f"- 데이터 타입 필터: {source_type}")
            
            # 필터 조건 구성
            where_clause = {}
            if department:
                where_clause["department"] = department
            if source_type:
                where_clause["source_type"] = source_type
            
            # 벡터 검색 수행
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 포맷팅
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0], 
                    results['distances'][0]
                )):
                    similarity = 1 - distance
                    result = {
                        'content': doc,
                        'metadata': metadata,
                        'similarity': similarity,
                        'relevance_score': similarity,
                        'distance': distance,
                        'rank': i + 1
                    }
                    formatted_results.append(result)
            
            search_end_time = datetime.now()
            search_duration = (search_end_time - search_start_time).total_seconds()
            
            # 검색 정보 저장
            self.last_search_info = {
                **search_params,
                "results_count": len(formatted_results),
                "search_duration_seconds": search_duration,
                "filters_applied": where_clause,
                "top_similarity": formatted_results[0]['similarity'] if formatted_results else 0
            }
            
            print(f"검색 완료: {len(formatted_results)}개 문서, {search_duration:.3f}초 소요")
            
            logger.info(f"검색 완료: {len(formatted_results)}개 문서 발견 (소요시간: {search_duration:.3f}초)")
            return formatted_results
            
        except Exception as e:
            logger.error(f"벡터 검색 중 오류: {e}")
            print(f"벡터 검색 오류: {e}")
            return []
    
    def get_context_for_llm(
            self, 
            query: str, 
            max_context_length: int = 2000,
            department: Optional[str] = None
        ) -> str:
        """
        LLM에게 제공할 컨텍스트 문자열 생성
        
        Args:
            query: 사용자 질의
            max_context_length: 최대 컨텍스트 길이
            department: 진료과 필터링
            
        Returns:
            str: LLM용 컨텍스트 문자열
        """
        print(f"\nRAG 컨텍스트 생성 시작")
        print(f"- 질의: {query[:100]}...")
        print(f"- 최대 길이: {max_context_length} 문자")
        
        # 다양한 소스에서 검색
        corpus_docs = self.search_relevant_documents(
            query, n_results=3, department=department, source_type="corpus"
        )
        qa_docs = self.search_relevant_documents(
            query, n_results=2, department=department, source_type="qa_answer"
        )
        
        # 컨텍스트 구성
        context_parts = []
        current_length = 0
        
        # 현재 시간 정보
        current_time = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
        time_info = f"현재 시간: {current_time}\n\n"
        context_parts.append(time_info)
        current_length += len(time_info)
        
        # 벡터 DB 사용 정보 추가
        vector_info = f"[벡터 DB 활용 정보]\n"
        vector_info += f"- 연결 상태: {self.connection_status}\n"
        vector_info += f"- 검색된 말뭉치 문서: {len(corpus_docs)}개\n"
        vector_info += f"- 검색된 Q&A 문서: {len(qa_docs)}개\n"
        vector_info += f"- 컬렉션: {self.collection_name}\n\n"
        context_parts.append(vector_info)
        current_length += len(vector_info)
        
        # 말뭉치 데이터 추가
        if corpus_docs:
            context_parts.append("=== 관련 의료 정보 (말뭉치 데이터) ===\n")
            current_length += len("=== 관련 의료 정보 (말뭉치 데이터) ===\n")
            
            for i, doc in enumerate(corpus_docs):
                if current_length >= max_context_length:
                    break
                content = doc['content'][:500]  # 내용 제한
                dept = doc['metadata'].get('department', '')
                similarity = doc['similarity']
                dept_info = f"[{dept}] " if dept else ""
                
                section = f"{i+1}. {dept_info}(유사도: {similarity:.3f}) {content}\n\n"
                if current_length + len(section) <= max_context_length:
                    context_parts.append(section)
                    current_length += len(section)
        
        # Q&A 데이터 추가
        if qa_docs and current_length < max_context_length:
            context_parts.append("=== 관련 질의응답 (Q&A 데이터) ===\n")
            current_length += len("=== 관련 질의응답 (Q&A 데이터) ===\n")
            
            for i, doc in enumerate(qa_docs):
                if current_length >= max_context_length:
                    break
                content = doc['content'][:300]
                dept = doc['metadata'].get('department', '')
                similarity = doc['similarity']
                dept_info = f"[{dept}] " if dept else ""
                
                section = f"{i+1}. {dept_info}(유사도: {similarity:.3f}) {content}\n\n"
                if current_length + len(section) <= max_context_length:
                    context_parts.append(section)
                    current_length += len(section)
        
        context = "".join(context_parts)
        
        # 검색된 문서가 없는 경우
        if len(corpus_docs) == 0 and len(qa_docs) == 0:
            no_docs_info = "관련 의료 정보를 벡터 DB에서 찾을 수 없습니다. 일반적인 의료 지식을 바탕으로 답변해드리겠습니다.\n\n"
            context += no_docs_info
        
        print(f"- 생성된 컨텍스트 길이: {len(context)} 문자")
        print(f"- 활용된 문서: 말뭉치 {len(corpus_docs)}개, Q&A {len(qa_docs)}개")
        
        return context
    
    def health_check(self) -> bool:
        """
        ChromaDB 연결 상태 확인
        
        Returns:
            bool: 연결 상태 (True: 정상, False: 실패)
        """
        try:
            if self.collection:
                count = self.collection.count()
                print(f"ChromaDB 상태 확인: 정상 연결, {count:,}개 문서")
                logger.info(f"ChromaDB 연결 정상: {count:,}개 문서")
                return True
            else:
                print(f"ChromaDB 상태 확인: 연결 없음")
                return False
        except Exception as e:
            print(f"ChromaDB 상태 확인 실패: {e}")
            logger.error(f"ChromaDB 연결 확인 실패: {e}")
            return False

    def get_search_statistics(self) -> Dict[str, Any]:
        """
        검색 통계 정보 반환
        
        Returns:
            Dict: 검색 통계 정보
        """
        return {
            "connection_info": self.get_connection_status(),
            "last_search": self.last_search_info,
            "available_filters": {
                "departments": getattr(self, 'available_departments', []),
                "source_types": getattr(self, 'available_source_types', [])
            }
        }