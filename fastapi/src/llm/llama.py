'''
파일은 LlamaModel, BaseConfig.OfficePrompt 클래스를 정의하고 llama_cpp_cuda를 사용하여,
Meta-Llama-3.1-8B-Claude.Q4_0.gguf 모델을 사용하여 대화를 생성하는 데 필요한 모든 기능을 제공합니다.
RAG(Retrieval-Augmented Generation) 기능이 추가되었습니다.
'''
from typing import Optional, Generator, List, Dict
from llama_cpp_cuda import Llama

import os
import sys
import json
import warnings
import time
from queue import Queue
from threading import Thread
from contextlib import contextmanager
from datetime import datetime

from domain import BaseConfig

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def build_llama3_prompt(
        character_info: BaseConfig.OfficePrompt, 
        vector_context: str = ""
    ) -> str:
    """
    RAG 컨텍스트를 포함한 Llama3 GGUF 형식의 프롬프트 문자열을 생성합니다.

    Args:
        character_info (BaseConfig.OfficePrompt): 캐릭터 기본 정보 및 대화 맥락 포함 객체
        vector_context (str): 벡터 검색으로 얻은 관련 문서 컨텍스트

    Returns:
        str: Llama3 GGUF 포맷용 프롬프트 문자열
    """
    # 벡터 검색 컨텍스트와 기존 참고 정보 결합
    reference_data = vector_context if vector_context else character_info.reference_data
    
    system_prompt = (
        f"당신은 AI 어시스턴트 {character_info.name}입니다.\n"
        f"당신의 역할: {character_info.context}\n\n"
        f"참고 정보 (사용자의 질문과 관련 있을 경우에만 활용하세요):\n"
        f"{reference_data}\n\n"
        f"지시 사항:\n"
        f"- 한국어로 답변하세요\n"
        f"- 친절하고 유익한 답변을 제공하세요\n"
        f"- 위의 참고 정보를 우선적으로 활용하되, 질문과 관련 없는 정보는 언급하지 마세요\n"
        f"- 의료 정보는 정확하고 신중하게 제공하며, 전문의 상담을 권유하세요\n"
        f"- 간결하면서도 핵심적인 정보를 포함하도록 하세요\n"
    )

    # 시스템 프롬프트 시작
    prompt = (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        f"{system_prompt}<|eot_id|>"
    )

    # 대화 기록 추가
    if character_info.chat_list:
        for chat in character_info.chat_list:
            user_input = chat.get("content", chat.get("input_data", ""))
            assistant_output = chat.get("answer", chat.get("output_data", ""))

            if user_input:
                prompt += (
                    "<|start_header_id|>user<|end_header_id|>\n"
                    f"{user_input}<|eot_id|>"
                )
            if assistant_output:
                prompt += (
                    "<|start_header_id|>assistant<|end_header_id|>\n"
                    f"{assistant_output}<|eot_id|>"
                )

    # 최신 사용자 입력 추가
    prompt += (
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{character_info.user_input}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )

    return prompt

class LlamaModel:
    """
    GGUF 포맷 llama-3-Korean-Bllossom-8B 모델 클래스
    외부에서 제공받은 검색 컨텍스트를 바탕으로 응답을 생성합니다.
    """
    def __init__(self, enable_rag: bool = True) -> None:
        """
        LlamaModel 클래스 초기화 메소드
        
        Args:
            enable_rag: RAG 기능 활성화 여부 (호환성을 위해 유지하지만 내부적으로 사용하지 않음)
        """
        self.model_id = 'llama-3-Korean-Bllossom-8B'
        self.model_path = "/app/fastapi/models/llama-3-Korean-Bllossom-8B.gguf"
        self.file_path = "/app/prompt/config-Llama.json"
        self.loading_text = f"{BLUE}LOADING{RESET}:    {self.model_id} 로드 중..."
        self.character_info: Optional[BaseConfig.OfficePrompt] = None
        self.config: Optional[BaseConfig.LlamaGenerationConfig] = None
        
        print("\n"+ f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text))
        print(f"{BLUE}LOADING{RESET}:    {__class__.__name__} 모델 초기화 시작...")

        # JSON 파일 읽기
        with open(self.file_path, 'r', encoding = 'utf-8') as file:
            self.data: BaseConfig.BaseConfig = json.load(file)

        # 진행 상태 표시
        print(f"{BLUE}LOADING{RESET}:    {__class__.__name__} 모델 초기화 중...")
        self.model: Llama = self._load_model()
        print(f"{BLUE}LOADING{RESET}:    모델 로드 완료!")
        print(f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text) + "\n")
        
        self.response_queue: Queue = Queue()

    def _load_model(self) -> Llama:
        """
        GGUF 포맷의 Llama 모델을 로드하고 GPU 가속을 최대화합니다.
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
                    main_gpu = 1,                       # 1번 GPU 사용 (office 서비스용)
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
            print(f"❌ 모델 로드 중 오류 발생: {e}")
            raise e

    def _stream_completion(self, config: BaseConfig.LlamaGenerationConfig) -> None:
        """
        별도 스레드에서 실행되어 응답을 큐에 넣는 메서드 (최적화)

        Args:
            config (BaseConfig.LlamaGenerationConfig): 생성 파라미터 객체
        """
        try:
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
                        
            print(f"    생성된 토큰 수: {token_count}")
            self.response_queue.put(None)  # 스트림 종료 신호
            
        except Exception as e:
            print(f"스트리밍 중 오류 발생: {e}")
            self.response_queue.put(None)

    def create_streaming_completion(self, config: BaseConfig.LlamaGenerationConfig) -> Generator[str, None, None]:
        """
        스트리밍 방식으로 텍스트 응답 생성

        Args:
            config (BaseConfig.LlamaGenerationConfig): 생성 파라미터 객체

        Returns:
            Generator[str, None, None]: 생성된 텍스트 조각들을 반환하는 제너레이터
        """
        # 큐 초기화 (이전 응답이 남아있을 수 있음)
        while not self.response_queue.empty():
            self.response_queue.get()
            
        # 스트리밍 스레드 시작
        thread = Thread(
            target = self._stream_completion,
            args = (config,)
        )
        thread.start()

        # 응답 스트리밍
        token_count = 0
        while True:
            text = self.response_queue.get()
            if text is None:  # 스트림 종료
                break
            token_count += 1
            yield text
            
        # 스레드가 완료될 때까지 대기
        thread.join()
        print(f"    스트리밍 완료: {token_count}개 토큰 수신")

    def create_completion(self, config: BaseConfig.LlamaGenerationConfig) -> str:
        """
        주어진 프롬프트로부터 텍스트 응답 생성

        Args:
            config (BaseConfig.LlamaGenerationConfig): 생성 파라미터 객체

        Returns:
            str: 생성된 텍스트 응답
        """
        try:
            output = self.model.create_completion(
                prompt = config.prompt,
                max_tokens = config.max_tokens,
                temperature = config.temperature,
                top_p = config.top_p,
                stop = config.stop or ["<|eot_id|>"]
            )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            print(f"응답 생성 중 오류 발생: {e}")
            return ""

    def generate_response(self, input_text: str, search_text: str, chat_list: List[Dict]) -> str:
        """
        외부에서 제공받은 검색 컨텍스트를 활용한 응답 생성 메서드

        Args:
            input_text (str): 사용자 입력 텍스트
            search_text (str): 외부에서 제공받은 검색 컨텍스트
            chat_list (List[Dict]): 대화 기록

        Returns:
            str: 생성된 텍스트
        """
        start_time = time.time()
        try:
            # 외부에서 제공받은 검색 컨텍스트 사용
            if search_text:
                print(f"    ✅ 외부 검색 컨텍스트 활용: {len(search_text)} 문자")
                reference_text = search_text
            else:
                # 검색 컨텍스트가 없는 경우 기본 정보 사용
                current_time = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
                reference_text = f"현재 시간은 {current_time}입니다.\n\n"
                print(f"    ⚠️ 검색 컨텍스트 없음, 기본 정보 사용")

            # 대화 기록 정규화 - MongoDB 구조에 맞게 수정
            normalized_chat_list = []
            if chat_list and len(chat_list) > 0:
                for chat in chat_list:
                    # MongoDB에서 가져온 메시지 구조에 맞게 수정
                    normalized_chat = {
                        "index": chat.get("message_idx", chat.get("index")),
                        "input_data": chat.get("content", chat.get("input_data", "")),
                        "output_data": self._normalize_escape_chars(
                            chat.get("answer", chat.get("output_data", ""))
                        )
                    }
                    normalized_chat_list.append(normalized_chat)
            else:
                normalized_chat_list = []

            # 캐릭터 정보 설정
            self.character_info = BaseConfig.OfficePrompt(
                name = self.data.get("character_name", "AI Assistant"),
                context = self.data.get("character_setting", "Helpful AI assistant"),
                reference_data = reference_text,
                user_input = input_text,
                chat_list = normalized_chat_list,
            )

            # RAG 프롬프트 생성
            prompt = build_llama3_prompt(
                character_info=self.character_info,
                vector_context=reference_text
            )
            
            # 균형 잡힌 설정으로 수정
            self.config = BaseConfig.LlamaGenerationConfig(
                prompt = prompt,
                max_tokens = 1024,                  # 적절한 토큰 수
                temperature = 0.7,                  # 온도 적절히 조정
                top_p = 0.9,                        # top_p 복원
                min_p = 0.1,                        # min_p 복원
                typical_p = 1.0,                    # typical_p 추가
                tfs_z = 1.1,                        # tfs_z 복원
                repeat_penalty = 1.08,              # repeat_penalty 복원
                frequency_penalty = 0.1,            # frequency_penalty 복원
                presence_penalty = 0.1,             # presence_penalty 복원
                seed = None,                        # 시드 없음 (다양성 확보)
            )
            
            print(f"    🚀 응답 생성 시작...")
            chunks = []
            for text_chunk in self.create_streaming_completion(config = self.config):
                chunks.append(text_chunk)
            
            result = "".join(chunks)
            generation_time = time.time() - start_time
            print(f"    ✅ 응답 생성 완료 (소요 시간: {generation_time:.2f}초)")
            return result

        except Exception as e:
            generation_time = time.time() - start_time
            print(f"❌ 응답 생성 중 오류 발생: {e} (소요 시간: {generation_time:.2f}초)")
            return f"오류: {str(e)}"

    def _normalize_escape_chars(self, text: str) -> str:
        """
        이스케이프 문자가 중복된 문자열을 정규화합니다
        """
        if not text:
            return ""
            
        # 이스케이프된 개행문자 등을 정규화
        result = text.replace("\\n", "\n")
        result = result.replace("\\\\n", "\n")
        result = result.replace('\\"', '"')
        result = result.replace("\\\\", "\\")
        
        return result
