"""
ChromaDB 벡터 검색 클라이언트
RAG(Retrieval-Augmented Generation)를 위한 벡터 검색 기능 제공
"""
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorSearchClient:
    """
    ChromaDB를 사용한 벡터 검색 클라이언트
    의료 데이터에서 관련 문서를 검색하여 LLM에게 컨텍스트 제공
    """
    
    def __init__(self, 
                    chroma_host: str = "localhost", 
                    chroma_port: int = 8000,
                    collection_name: str = "vet_medical_data"
        ):
        """
        벡터 검색 클라이언트 초기화
        
        Args:
            chroma_host: ChromaDB 호스트
            chroma_port: ChromaDB 포트  
            collection_name: 컬렉션 이름
        """
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.collection_name = collection_name
        self.connection_status = "NOT_CONNECTED"
        self.last_search_info = {}
        
        # HTTP 로그 숨기기
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("chromadb").setLevel(logging.ERROR)
        
        try:
            print(f"🔗 ChromaDB 연결 시도: {chroma_host}:{chroma_port}")
            
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(
                    allow_reset=True,
                    anonymized_telemetry=False
                )
            )
            
            # 컬렉션 가져오기
            self.collection = self.client.get_collection(name=collection_name)
            
            # 연결 성공 시 정보 수집
            collection_count = self.collection.count()
            self.connection_status = "CONNECTED"
            
            print(f"✅ ChromaDB 연결 성공!")
            print(f"📊 컬렉션: {collection_name}")
            print(f"📄 문서 수: {collection_count:,}개")
            
            # 컬렉션 메타데이터 정보 수집
            self._collect_collection_info()
            
            logger.info(f"벡터 검색 클라이언트 초기화 완료: {collection_name} ({collection_count:,}개 문서)")
            
        except Exception as e:
            self.connection_status = "CONNECTION_FAILED"
            self.collection = None
            print(f"❌ ChromaDB 연결 실패: {e}")
            logger.error(f"ChromaDB 연결 실패: {e}")

    def _collect_collection_info(self):
        """컬렉션 정보 수집"""
        try:
            # 샘플 데이터 조회하여 스키마 파악
            sample_results = self.collection.peek(limit=5)
            
            departments = set()
            source_types = set()
            
            if sample_results.get('metadatas'):
                for metadata in sample_results['metadatas']:
                    if metadata:
                        if 'department' in metadata:
                            departments.add(metadata['department'])
                        if 'source_type' in metadata:
                            source_types.add(metadata['source_type'])
            
            self.available_departments = list(departments)
            self.available_source_types = list(source_types)
            
            print(f"🏥 사용 가능한 진료과: {', '.join(self.available_departments)}")
            print(f"📚 사용 가능한 데이터 타입: {', '.join(self.available_source_types)}")
            
        except Exception as e:
            print(f"⚠️  컬렉션 정보 수집 실패: {e}")
            self.available_departments = []
            self.available_source_types = []

    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
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

    def search_relevant_documents(self, 
                                query: str, 
                                n_results: int = 5,
                                department: Optional[str] = None,
                                source_type: Optional[str] = None) -> List[Dict[str, Any]]:
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
            
            print(f"🔍 벡터 검색 실행:")
            print(f"   📝 질의: {search_params['query']}")
            print(f"   🎯 요청 결과 수: {n_results}")
            if department:
                print(f"   🏥 진료과 필터: {department}")
            if source_type:
                print(f"   📚 데이터 타입 필터: {source_type}")
            
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
                    
                    # 검색 결과 로깅 (상위 3개만)
                    if i < 3:
                        dept = metadata.get('department', 'Unknown')
                        src_type = metadata.get('source_type', 'Unknown')
                        content_preview = doc[:80] + "..." if len(doc) > 80 else doc
                        print(f"   📋 결과 {i+1}: [{dept}] [{src_type}] 유사도:{similarity:.3f}")
                        print(f"      💭 내용: {content_preview}")
            
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
            
            print(f"   ✅ 검색 완료: {len(formatted_results)}개 문서, {search_duration:.3f}초 소요")
            
            logger.info(f"검색 완료: {len(formatted_results)}개 문서 발견 (소요시간: {search_duration:.3f}초)")
            return formatted_results
            
        except Exception as e:
            logger.error(f"벡터 검색 중 오류: {e}")
            print(f"❌ 벡터 검색 오류: {e}")
            return []
    
    def get_context_for_llm(self, 
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
        print(f"\n📊 RAG 컨텍스트 생성 시작")
        print(f"   🎯 질의: {query[:100]}...")
        print(f"   📏 최대 길이: {max_context_length} 문자")
        
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
            no_docs_info = "⚠️ 관련 의료 정보를 벡터 DB에서 찾을 수 없습니다. 일반적인 의료 지식을 바탕으로 답변해드리겠습니다.\n\n"
            context += no_docs_info
        
        print(f"   📝 생성된 컨텍스트 길이: {len(context)} 문자")
        print(f"   📊 활용된 문서: 말뭉치 {len(corpus_docs)}개, Q&A {len(qa_docs)}개")
        
        return context
    
    def health_check(self) -> bool:
        """ChromaDB 연결 상태 확인"""
        try:
            if self.collection:
                count = self.collection.count()
                print(f"✅ ChromaDB 상태 확인: 정상 연결, {count:,}개 문서")
                logger.info(f"ChromaDB 연결 정상: {count:,}개 문서")
                return True
            else:
                print(f"❌ ChromaDB 상태 확인: 연결 없음")
                return False
        except Exception as e:
            print(f"❌ ChromaDB 상태 확인 실패: {e}")
            logger.error(f"ChromaDB 연결 확인 실패: {e}")
            return False

    def get_search_statistics(self) -> Dict[str, Any]:
        """검색 통계 정보 반환"""
        return {
            "connection_info": self.get_connection_status(),
            "last_search": self.last_search_info,
            "available_filters": {
                "departments": getattr(self, 'available_departments', []),
                "source_types": getattr(self, 'available_source_types', [])
            }
        }