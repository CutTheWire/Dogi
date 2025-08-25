'''
파일은 LlamaModel, BaseConfig.OfficePrompt 클래스를 정의하고 llama_cpp_cuda를 사용하여,
Meta-Llama-3.1-8B-Claude.Q4_0.gguf 모델을 사용하여 대화를 생성하는 데 필요한 모든 기능을 제공합니다.
ChromaDB는 LangChain으로 연결하고, 모델은 llama_cpp_cuda로 직접 서빙합니다.
'''
from typing import  Generator, List, Dict
from llama_cpp_cuda import Llama

import os
import sys
import json
import textwrap
import warnings
import time
from queue import Queue
from threading import Thread
from contextlib import contextmanager
from datetime import datetime

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
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>
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
        - 간결하면서도 핵심적인 정보를 포함하도록 하세요<|eot_id|>

        <|start_header_id|>user<|end_header_id|>
        {question}<|eot_id|>

        <|start_header_id|>assistant<|end_header_id|>
    """).strip()
        
    return PromptTemplate(
        template=template,
        input_variables=["context", "chat_history", "question"]
    )

class LlamaModel:
    """
    llama_cpp_cuda로 모델 서빙 + LangChain으로 ChromaDB 연결하는 RAG 시스템
    """
    def __init__(self) -> None:
        """
        LlamaModel 클래스 초기화 메소드
        """
        self.model_id = 'llama-3-Korean-Bllossom-8B'
        self.model_path = "/app/fastapi/models/llama-3-Korean-Bllossom-8B.gguf"
        self.file_path = "/app/prompt/config-Llama.json"
        self.loading_text = f"{BLUE}LOADING{RESET}:    {self.model_id} 로드 중..."
        
        print("\n"+ f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text))
        print(f"{BLUE}LOADING{RESET}:    {__class__.__name__} 모델 초기화 시작...")

        # JSON 파일 읽기
        with open(self.file_path, 'r', encoding = 'utf-8') as file:
            self.data: BaseConfig.BaseConfig = json.load(file)

        # llama_cpp_cuda로 모델 로드
        print(f"{BLUE}LOADING{RESET}:    llama_cpp_cuda로 모델 로드 중...")
        self.model: Llama = self._load_model()
        print(f"{BLUE}LOADING{RESET}:    llama_cpp_cuda 모델 로드 완료!")
        
        # ChromaDB + LangChain RAG 컴포넌트 초기화
        self._initialize_rag_components()
        
        print(f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text) + "\n")
        
        self.response_queue: Queue = Queue()

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
                content = doc.page_content[:500]
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
                content = doc.page_content[:300]
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
        for chat in chat_list[-3:]:
            user_msg = chat.get("content", chat.get("input_data", ""))
            ai_msg = chat.get("answer", chat.get("output_data", ""))
            
            if user_msg:
                formatted_history.append(f"사용자: {user_msg}")
            if ai_msg:
                formatted_history.append(f"AI: {ai_msg}")
        
        return "\n".join(formatted_history)

    def _load_model(self) -> Llama:
        """
        llama_cpp_cuda를 사용해 GGUF 포맷의 Llama 모델을 로드
        """
        print(f"{self.loading_text}")
        try:
            warnings.filterwarnings("ignore")
            
            @contextmanager
            def suppress_stdout():
                with open(os.devnull, "w") as devnull:
                    old_stdout = sys.stdout
                    sys.stdout = devnull
                    try:
                        yield
                    finally:
                        sys.stdout = old_stdout

            # GPU 사용량 극대화를 위한 설정
            with suppress_stdout():
                model = Llama(
                    model_path = self.model_path,       # GGUF 모델 파일 경로
                    n_gpu_layers = -1,                  # 모든 레이어를 GPU에 로드
                    main_gpu = 0,                       # 0번 GPU 사용 (수정)
                    rope_scaling_type = 2,              # RoPE 스케일링 방식 (2 = linear) 
                    rope_freq_scale = 2.0,              # RoPE 주파수 스케일 → 긴 문맥 지원   
                    n_ctx = 8191,                       # 최대 context length
                    n_batch = 2048,                     # 배치 크기 (VRAM 제한 고려한 중간 값)
                    verbose = False,                    # 디버깅 로그 비활성화  
                    offload_kqv = True,                 # K/Q/V 캐시를 CPU로 오프로드하여 VRAM 절약
                    use_mmap = False,                   # 메모리 매핑 비활성화 
                    use_mlock = True,                   # 메모리 잠금으로 메모리 페이지 스왑 방지
                    n_threads = 12,                     # CPU 스레드 수 (코어 12개 기준 적절한 값)
                    tensor_split = [1.0],               # 단일 GPU에서 모든 텐서 로딩
                    split_mode = 1,                     # 텐서 분할 방식 (1 = 균등 분할)
                    flash_attn = True,                  # FlashAttention 사용 (속도 향상)
                    cont_batching = True,               # 연속 배칭 활성화 (멀티 사용자 처리에 효율적)
                    numa = False,                       # NUMA 비활성화 (단일 GPU 시스템에서 불필요)
                    f16_kv = True,                      # 16bit KV 캐시 사용
                    logits_all = False,                 # 마지막 토큰만 logits 계산
                    embedding = False,                  # 임베딩 비활성화
                )
            return model
        except Exception as e:
            print(f"❌ llama_cpp_cuda 모델 로드 중 오류 발생: {e}")
            raise e

    def generate_response(self, input_text: str, chat_list: List[Dict]) -> str:
        """
        ChromaDB RAG + llama_cpp_cuda 모델을 활용한 응답 생성

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
        ChromaDB RAG + llama_cpp_cuda를 활용한 스트리밍 응답 생성

        Args:
            input_text (str): 사용자 입력 텍스트
            chat_list (List[Dict]): 대화 기록

        Yields:
            str: 생성된 텍스트 조각들
        """
        start_time = time.time()
        try:
            print(f"    🚀 ChromaDB RAG + llama_cpp_cuda 스트리밍 응답 생성 시작...")
            
            # RAG 가능 여부 확인
            if self.rag_available and self.retriever and self.prompt_template:
                # LangChain Retriever로 ChromaDB에서 관련 문서 검색
                docs = self.retriever.get_relevant_documents(input_text)
                context = self._format_documents(docs)
                
                # 대화 기록 포맷팅
                chat_history = self._format_chat_history(chat_list)
                
                # LangChain 프롬프트 템플릿으로 프롬프트 생성
                prompt = self.prompt_template.format(
                    context=context,
                    chat_history=chat_history,
                    question=input_text
                )
                
                print(f"    🔍 ChromaDB RAG 컨텍스트 포함 스트리밍 시작...")
                
                # llama_cpp_cuda로 스트리밍 생성
                config = BaseConfig.LlamaGenerationConfig(
                    prompt=prompt,
                    max_tokens=1024,
                    temperature=0.7,
                    top_p=0.9,
                    stop=["<|eot_id|>"]
                )
                
                # 스트리밍 생성
                for text_chunk in self.create_streaming_completion(config):
                    yield text_chunk
                    
                generation_time = time.time() - start_time
                print(f"    ✅ ChromaDB RAG + llama_cpp_cuda 스트리밍 완료 (소요 시간: {generation_time:.2f}초)")
                
            else:
                print(f"    ⚠️ ChromaDB RAG 기능 사용 불가, llama_cpp_cuda 기본 모드로 전환")
                # 폴백 스트리밍 (순수 llama_cpp_cuda)
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
        ChromaDB RAG 실패시 순수 llama_cpp_cuda로 스트리밍 응답 생성
        """
        try:
            print(f"    🔄 순수 llama_cpp_cuda 스트리밍 모드로 응답 생성...")
            
            # 기본 프롬프트 생성
            current_time = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
            
            # 시스템 프롬프트
            system_prompt = textwrap.dedent(f"""
                당신은 전문적인 반려동물 의료 상담 AI 어시스턴트입니다.
                현재 시간: {current_time}

                지시 사항:
                - 한국어로 정확하고 친절하게 답변하세요
                - 의료 정보는 정확하고 신중하게 제공하며, 응급상황이나 심각한 증상의 경우 즉시 전문의 상담을 권유하세요
                - 간결하면서도 핵심적인 정보를 포함하도록 하세요
            """).strip()

            # 대화 기록 포맷팅
            chat_history = self._format_chat_history(chat_list)
            
            # 전체 프롬프트 구성
            prompt = textwrap.dedent(f"""
                <|begin_of_text|><|start_header_id|>system<|end_header_id|>
                {system_prompt}

                대화 기록:
                {chat_history}<|eot_id|>

                <|start_header_id|>user<|end_header_id|>
                {input_text}<|eot_id|>

                <|start_header_id|>assistant<|end_header_id|>
            """).strip()
            
            # llama_cpp_cuda 스트리밍 설정
            config = BaseConfig.LlamaGenerationConfig(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.7,
                top_p=0.9,
                stop=["<|eot_id|>"]
            )
            
            # llama_cpp_cuda 스트리밍 생성
            for text_chunk in self.create_streaming_completion(config):
                yield text_chunk
        
        except Exception as e:
            print(f"❌ 순수 llama_cpp_cuda 스트리밍 모드 응답 생성 실패: {e}")
            yield f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"

    def _stream_completion(self, config: BaseConfig.LlamaGenerationConfig) -> None:
        """
        llama_cpp_cuda로 별도 스레드에서 실행되어 응답을 큐에 넣는 메서드 (스트리밍용)
        """
        try:
            # llama_cpp_cuda 스트리밍 생성
            stream = self.model.create_completion(
                prompt = config.prompt,
                max_tokens = config.max_tokens,
                temperature = config.temperature,
                top_p = config.top_p,
                min_p = config.min_p,
                typical_p = config.typical_p,
                tfs_z = config.tfs_z,
                repeat_penalty = config.repeat_penalty,
                frequency_penalty = config.frequency_penalty,
                presence_penalty = config.presence_penalty,
                stop = config.stop or ["<|eot_id|>"],
                stream = True,
                seed = config.seed,
            )
            
            token_count = 0
            for output in stream:
                if 'choices' in output and len(output['choices']) > 0:
                    text = output['choices'][0].get('text', '')
                    if text:
                        self.response_queue.put(text)
                        token_count += 1
                        
            print(f"    llama_cpp_cuda 생성된 토큰 수: {token_count}")
            self.response_queue.put(None)  # 스트림 종료 신호
            
        except Exception as e:
            print(f"llama_cpp_cuda 스트리밍 중 오류 발생: {e}")
            self.response_queue.put(None)

    def create_streaming_completion(self, config: BaseConfig.LlamaGenerationConfig) -> Generator[str, None, None]:
        """
        llama_cpp_cuda로 스트리밍 방식으로 텍스트 응답 생성
        """
        # 큐 초기화
        while not self.response_queue.empty():
            self.response_queue.get()
            
        # llama_cpp_cuda 스트리밍 스레드 시작
        thread = Thread(
            target = self._stream_completion,
            args = (config,)
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
        print(f"    llama_cpp_cuda 스트리밍 완료: {token_count}개 토큰 수신")

