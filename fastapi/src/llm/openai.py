'''
파일은 OpenAIModel 클래스를 정의하고 OpenAI API를 사용하여,
GPT 모델을 사용하여 대화를 생성하는 데 필요한 모든 기능을 제공합니다.
ChromaDB는 LangChain으로 연결하고, 모델은 OpenAI API로 서빙합니다.
'''
from typing import  Generator, List, Dict
import os
import json
import textwrap
import time
from openai import OpenAI
from pathlib import Path
from queue import Queue
from threading import Thread
from datetime import datetime

from dotenv import load_dotenv
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.schema.retriever import BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from pydantic import Field

from service.vector_client import VectorSearchHandler
from domain import BaseConfig
from core import app_state as AppState

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

class VectorRetriever(BaseRetriever):
    """
    VectorSearchHandler를 LangChain Retriever로 래핑 (ChromaDB 연결용)
    """
    vector_handler: VectorSearchHandler = Field(description="ChromaDB 벡터 검색 핸들러")
    
    class Config:
        arbitrary_types_allowed = True
        
    def __init__(self, vector_handler: VectorSearchHandler, **kwargs):
        super().__init__(vector_handler=vector_handler, **kwargs)
    
    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        VectorSearchHandler에서 관련 문서를 검색하여 LangChain Document로 변환
        """
        if not self.vector_handler:
            print("    ⚠️ VectorSearchHandler가 없습니다.")
            return []
        
        try:
            print(f"    🔍 ChromaDB 벡터 검색 중: '{query[:50]}...'")
            
            # 말뭉치 데이터 검색
            corpus_results = self.vector_handler.search_relevant_documents(
                query=query,
                n_results=3,
                source_type="corpus"
            )
            
            # Q&A 데이터 검색
            qa_results = self.vector_handler.search_relevant_documents(
                query=query,
                n_results=2,
                source_type="qa_answer"
            )
            
            # 결과 합치기
            all_results = corpus_results + qa_results
            
            print(f"    📄 {len(all_results)}개 문서 검색됨 (말뭉치: {len(corpus_results)}, Q&A: {len(qa_results)})")
            
            # LangChain Document 형식으로 변환
            documents = []
            for result in all_results:
                doc = Document(
                    page_content=result.get('content', ''),
                    metadata={
                        **result.get('metadata', {}),
                        'similarity': result.get('similarity', 0),
                        'rank': result.get('rank', 0)
                    }
                )
                documents.append(doc)
            
            # 유사도 기준으로 정렬
            documents.sort(key=lambda x: x.metadata.get('similarity', 0), reverse=True)
            
            return documents[:5]
            
        except Exception as e:
            print(f"    ❌ ChromaDB 벡터 검색 중 오류 발생: {e}")
            return []

def build_rag_prompt_template() -> PromptTemplate:
    """
    RAG를 위한 프롬프트 템플릿 생성 (LangChain 템플릿 형식)
    """
    template = textwrap.dedent("""
        당신은 전문적인 반려동물 의료 상담 AI 어시스턴트입니다.
        아래 ChromaDB에서 검색된 의료 정보를 바탕으로 사용자의 질문에 답변해주세요.

        검색된 의료 정보:
        {context}

        대화 기록:
        {chat_history}

        지시 사항:
        - 한국어로 정확하고 친절하게 답변하세요
        - 검색된 의료 정보를 우선적으로 활용하세요
        - 의료 정보는 정확하고 신중하게 제공하며, 응급상황이나 심각한 증상의 경우 즉시 전문의 상담을 권유하세요
        - 검색된 정보가 질문과 직접적으로 관련이 없다면 일반적인 의료 지식을 바탕으로 답변하세요
        - 간결하면서도 핵심적인 정보를 포함하도록 하세요

        사용자 질문: {question}

        답변:
    """).strip()
    
    return PromptTemplate(
        template=template,
        input_variables=["context", "chat_history", "question"]
    )

class OpenAIModel:
    """
    OpenAI API로 모델 서빙 + LangChain으로 ChromaDB 연결하는 RAG 시스템
    """
    def __init__(self, model_id: str = "gpt-4.1") -> None:
        """
        OpenAIModel 클래스 초기화 메소드
        
        Args:
            model_id (str): 사용할 OpenAI 모델 ID (기본값: gpt-4.1)
        """
        self.model_id = model_id
        self.file_path = "/app/prompt/config-OpenAI.json"
        self.loading_text = f"{BLUE}LOADING{RESET}:    {self.model_id} 로드 중..."
        
        print("\n"+ f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text))
        print(f"{BLUE}LOADING{RESET}:    {__class__.__name__} 모델 초기화 시작...")

        # 환경변수에서 OpenAI API 키 로드
        self._load_api_key()

        # JSON 파일 읽기 (파일이 있는 경우에만)
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as file:
                self.data: BaseConfig.BaseConfig = json.load(file)
        else:
            # 기본 설정
            self.data = {
                "character_name": "Dogi AI",
                "greeting": "안녕하세요! 저는 Dogi AI입니다.",
                "character_setting": ["전문적인 반려동물 의료 상담 AI 어시스턴트"]
            }

        # OpenAI 클라이언트 초기화
        print(f"{BLUE}LOADING{RESET}:    OpenAI API 클라이언트 초기화 중...")
        self.client = OpenAI(api_key=self.api_key)
        print(f"{BLUE}LOADING{RESET}:    OpenAI API 클라이언트 초기화 완료!")
        
        # ChromaDB + LangChain RAG 컴포넌트 초기화
        self._initialize_rag_components()
        
        print(f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text) + "\n")
        
        self.response_queue: Queue = Queue()

    def _load_api_key(self):
        """
        .env 파일에서 OpenAI API 키를 로드합니다.
        """
        try:
            # .env 파일 경로 설정 (프로젝트 루트의 .env 파일)
            env_file_path = Path(__file__).resolve().parents[1] / ".env"
            load_dotenv(env_file_path)
            
            self.api_key = os.getenv("OPENAI_API_KEY")
            
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")
            
            print(f"{BLUE}LOADING{RESET}:    OpenAI API 키 로드 완료!")
            
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     OpenAI API 키 로드 실패: {e}")
            raise e

    def _initialize_rag_components(self):
        """
        ChromaDB 연결 + LangChain RAG 컴포넌트들 초기화
        """
        try:
            # VectorSearchHandler 초기화 (app_state에서 가져오기)
            self.vector_handler = AppState.get_vector_handler()
            
            if self.vector_handler and self.vector_handler.health_check():
                print(f"{BLUE}LOADING{RESET}:    ChromaDB 연결 확인 완료!")
                
                # LangChain Retriever 초기화 (ChromaDB 연결용)
                self.retriever = VectorRetriever(vector_handler=self.vector_handler)
                
                # 프롬프트 템플릿 생성
                self.prompt_template = build_rag_prompt_template()
                
                self.rag_available = True
                print(f"{BLUE}LOADING{RESET}:    LangChain RAG 컴포넌트 초기화 완료!")
                
            else:
                print(f"{YELLOW}WARNING{RESET}:  ChromaDB 연결 실패, RAG 기능 제한됨")
                self.retriever = None
                self.prompt_template = None
                self.rag_available = False
                
        except Exception as e:
            print(f"{RED}ERROR{RESET}:     RAG 컴포넌트 초기화 실패: {e}")
            self.retriever = None
            self.prompt_template = None
            self.rag_available = False

    def _format_documents(self, docs: List[Document]) -> str:
        """
        LangChain Document를 문자열로 포맷팅
        """
        if not docs:
            return "관련 정보를 찾을 수 없습니다."
        
        formatted_docs = []
        corpus_docs = []
        qa_docs = []
        
        # 문서 타입별로 분류
        for doc in docs:
            source_type = doc.metadata.get('source_type', '')
            if source_type == 'corpus':
                corpus_docs.append(doc)
            elif source_type in ['qa_answer', 'qa_question']:
                qa_docs.append(doc)
            else:
                corpus_docs.append(doc)
        
        # 말뭉치 문서 포맷팅
        if corpus_docs:
            formatted_docs.append("=== 관련 의료 정보 (말뭉치 데이터) ===")
            for i, doc in enumerate(corpus_docs, 1):
                content = doc.page_content
                metadata = doc.metadata
                
                doc_info = f"[문서 {i}]"
                if metadata.get('department'):
                    doc_info += f" (진료과: {metadata['department']})"
                if metadata.get('similarity'):
                    doc_info += f" (유사도: {metadata['similarity']:.3f})"
                
                formatted_docs.append(f"{doc_info}\n{content}")
        
        # Q&A 문서 포맷팅
        if qa_docs:
            formatted_docs.append("\n=== 관련 질의응답 (Q&A 데이터) ===")
            for i, doc in enumerate(qa_docs, 1):
                content = doc.page_content
                metadata = doc.metadata
                
                doc_info = f"[Q&A {i}]"
                if metadata.get('department'):
                    doc_info += f" (진료과: {metadata['department']})"
                if metadata.get('similarity'):
                    doc_info += f" (유사도: {metadata['similarity']:.3f})"
                
                formatted_docs.append(f"{doc_info}\n{content}")
        
        return "\n\n".join(formatted_docs)

    def _format_chat_history(self, chat_list: List[Dict]) -> str:
        """
        대화 기록을 문자열로 포맷팅
        """
        if not chat_list:
            return "이전 대화 없음"
        
        formatted_history = []
        for chat in chat_list[-3:]:  # 최근 3개 대화만 포함
            user_msg = chat.get("content", chat.get("input_data", ""))
            ai_msg = chat.get("answer", chat.get("output_data", ""))
            
            if user_msg:
                formatted_history.append(f"사용자: {user_msg}")
            if ai_msg:
                formatted_history.append(f"AI: {ai_msg}")
        
        return "\n".join(formatted_history)

    def _convert_chat_to_messages(self, chat_list: List[Dict], current_input: str, context: str = None) -> List[Dict]:
        """
        대화 기록을 OpenAI API 메시지 형식으로 변환
        """
        messages = []
        
        # 시스템 메시지 추가
        current_time = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
        
        system_content = textwrap.dedent(f"""
            당신은 전문적인 반려동물 의료 상담 AI 어시스턴트입니다.
            현재 시간: {current_time}

            지시 사항:
            - 한국어로 정확하고 친절하게 답변하세요
            - 의료 정보는 정확하고 신중하게 제공하며, 응급상황이나 심각한 증상의 경우 즉시 전문의 상담을 권유하세요
            - 간결하면서도 핵심적인 정보를 포함하도록 하세요
        """).strip()

        if context:
            system_content += f"\n\n참고할 의료 정보:\n{context}"

        messages.append({
            "role": "system",
            "content": system_content
        })
        
        # 대화 기록 추가 (최근 5개만)
        for chat in chat_list[-5:]:
            user_msg = chat.get("content", chat.get("input_data", ""))
            ai_msg = chat.get("answer", chat.get("output_data", ""))
            
            if user_msg:
                messages.append({
                    "role": "user",
                    "content": user_msg
                })
            if ai_msg:
                messages.append({
                    "role": "assistant",
                    "content": ai_msg
                })
        
        # 현재 사용자 입력 추가
        messages.append({
            "role": "user",
            "content": current_input
        })
        
        return messages

    def generate_response(self, input_text: str, chat_list: List[Dict]) -> str:
        """
        ChromaDB RAG + OpenAI API를 활용한 응답 생성

        Args:
            input_text (str): 사용자 입력 텍스트
            chat_list (List[Dict]): 대화 기록

        Returns:
            str: 생성된 텍스트
        """
        chunks = []
        for chunk in self.generate_response_stream(input_text, chat_list):
            chunks.append(chunk)
        return "".join(chunks)

    def generate_response_stream(self, input_text: str, chat_list: List[Dict]) -> Generator[str, None, None]:
        """
        ChromaDB RAG + OpenAI API를 활용한 스트리밍 응답 생성

        Args:
            input_text (str): 사용자 입력 텍스트
            chat_list (List[Dict]): 대화 기록

        Yields:
            str: 생성된 텍스트 조각들
        """
        start_time = time.time()
        try:
            print(f"    🚀 ChromaDB RAG + OpenAI API 스트리밍 응답 생성 시작...")
            
            # RAG 가능 여부 확인
            if self.rag_available and self.retriever:
                # LangChain Retriever로 ChromaDB에서 관련 문서 검색
                docs = self.retriever.get_relevant_documents(input_text)
                context = self._format_documents(docs)
                
                print(f"    🔍 ChromaDB RAG 컨텍스트 포함 스트리밍 시작...")
                
                # OpenAI API 메시지 형식으로 변환
                messages = self._convert_chat_to_messages(chat_list, input_text, context)
                
                # OpenAI API 설정
                config = BaseConfig.OpenAIGenerationConfig(
                    messages=messages,
                    max_tokens=4096,
                    temperature=1.0,
                )
                
                # 스트리밍 생성
                for text_chunk in self.create_streaming_completion(config):
                    yield text_chunk
                    
                generation_time = time.time() - start_time
                print(f"    ✅ ChromaDB RAG + OpenAI API 스트리밍 완료 (소요 시간: {generation_time:.2f}초)")
                
            else:
                print(f"    ⚠️ ChromaDB RAG 기능 사용 불가, OpenAI API 기본 모드로 전환")
                # 폴백 스트리밍 (순수 OpenAI API)
                for text_chunk in self._generate_fallback_response_stream(input_text, chat_list):
                    yield text_chunk

        except Exception as e:
            generation_time = time.time() - start_time
            print(f"❌ ChromaDB RAG 스트리밍 중 오류 발생: {e} (소요 시간: {generation_time:.2f}초)")
            # 에러 시 폴백 스트리밍
            for text_chunk in self._generate_fallback_response_stream(input_text, chat_list):
                yield text_chunk

    def _generate_fallback_response_stream(self, input_text: str, chat_list: List[Dict]) -> Generator[str, None, None]:
        """
        ChromaDB RAG 실패시 순수 OpenAI API로 스트리밍 응답 생성
        """
        try:
            print(f"    🔄 순수 OpenAI API 스트리밍 모드로 응답 생성...")
            
            # OpenAI API 메시지 형식으로 변환
            messages = self._convert_chat_to_messages(chat_list, input_text)
            
            # OpenAI API 설정
            config = BaseConfig.OpenAIGenerationConfig(
                messages=messages,
                max_tokens=4096,
                temperature=1.0,
            )
            
            # OpenAI API 스트리밍 생성
            for text_chunk in self.create_streaming_completion(config):
                yield text_chunk
            
        except Exception as e:
            print(f"❌ 순수 OpenAI API 스트리밍 모드 응답 생성 실패: {e}")
            yield f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"

    def _stream_completion(self, config: BaseConfig.OpenAIGenerationConfig) -> None:
        """
        OpenAI Responses API로 별도 스레드에서 실행되어 응답을 큐에 넣는 메서드 (스트리밍용)
        """
        try:
            # Responses API 스트리밍 시도
            stream = self.client.responses.create(
                model=self.model_id,
                input=config.messages,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                stream=True,
            )

            token_count = 0
            for event in stream:
                # 텍스트 델타 이벤트만 전송
                if getattr(event, "type", None) == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        self.response_queue.put(delta)
                        token_count += 1
                elif getattr(event, "type", None) in ("response.completed", "response.error"):
                    break

            print(f"    OpenAI API 생성된 토큰 수: {token_count}")
            self.response_queue.put(None)

        except Exception as e:
            err_msg = str(e)
            print(f"OpenAI API 스트리밍 중 오류 발생: {e}")
            try:
                resp = self.client.responses.create(
                    model=self.model_id,
                    input=config.messages,
                    max_output_tokens=config.max_tokens,
                    temperature=config.temperature,
                )
                # 편의 프로퍼티 (SDK가 제공)
                content = getattr(resp, "output_text", None)
                if not content:
                    # 구조형 응답 합치기 (보수적 처리)
                    content_parts = []
                    for out in getattr(resp, "output", []) or []:
                        for c in getattr(out, "content", []) or []:
                            text = getattr(getattr(c, "text", None), "value", None)
                            if text:
                                content_parts.append(text)
                    content = "".join(content_parts)
                if content:
                    self.response_queue.put(content)
                self.response_queue.put(None)
            except Exception as e2:
                print(f"OpenAI API 비스트리밍 재시도 실패: {e2}")
                self.response_queue.put("죄송합니다. 현재 모델로는 스트리밍이 제한되어 있습니다. 잠시 후 다시 시도해주세요.")
                self.response_queue.put(None)

    def create_streaming_completion(self, config: BaseConfig.OpenAIGenerationConfig) -> Generator[str, None, None]:
        """
        OpenAI API로 스트리밍 방식으로 텍스트 응답 생성
        """
        # 큐 초기화
        while not self.response_queue.empty():
            self.response_queue.get()
            
        # OpenAI API 스트리밍 스레드 시작
        thread = Thread(
            target=self._stream_completion,
            args=(config,)
        )
        thread.start()

        # 응답 스트리밍
        token_count = 0
        while True:
            text = self.response_queue.get()
            if text is None:
                break
            token_count += 1
            yield text
            
        # 스레드가 완료될 때까지 대기
        thread.join()
        print(f"    OpenAI API 스트리밍 완료: {token_count}개 토큰 수신")