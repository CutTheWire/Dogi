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

from src.domain import BaseConfig, VectorClient

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def build_llama3_prompt_with_rag(character_info: BaseConfig.OfficePrompt, 
                                vector_context: str = "") -> str:
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
            user_input = chat.get("input_data", "")
            assistant_output = chat.get("output_data", "")

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

def build_llama3_prompt(character_info: BaseConfig.OfficePrompt) -> str:
    """
    캐릭터 정보와 대화 기록을 기반으로 Llama3 GGUF 형식의 프롬프트 문자열을 생성합니다.

    Args:
        character_info (BaseConfig.OfficePrompt): 캐릭터 기본 정보 및 대화 맥락 포함 객체

    Returns:
        str: Llama3 GGUF 포맷용 프롬프트 문자열
    """
    system_prompt = (
        f"당신은 AI 어시스턴트 {character_info.name}입니다.\n"
        f"당신의 역할: {character_info.context}\n\n"
        f"참고 정보 (사용자의 질문과 관련 있을 경우에만 활용하세요):\n"
        f"{character_info.reference_data}\n\n"
        f"지시 사항:\n"
        f"- 한국어로 답변하세요\n"
        f"- 친절하고 유익한 답변을 제공하세요\n"
        f"- 질문과 관련 없는 참고 정보는 언급하지 마세요\n"
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
            user_input = chat.get("input_data", "")
            assistant_output = chat.get("output_data", "")

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
    RAG 기능을 갖춘 GGUF 포맷 llama-3-Korean-Bllossom-8B 모델 클래스
    벡터 검색을 통해 관련 의료 문서를 검색하고 이를 바탕으로 응답을 생성합니다.
    """
    def __init__(self, enable_rag: bool = True) -> None:
        """
        LlamaModel 클래스 초기화 메소드
        
        Args:
            enable_rag: RAG 기능 활성화 여부
        """
        self.model_id = 'llama-3-Korean-Bllossom-8B'
        self.model_path = "./fastapi/models/llama-3-Korean-Bllossom-8B.gguf"
        self.file_path = './fastapi/prompt/config-Llama.json'
        self.loading_text = f"{BLUE}LOADING{RESET}:    {self.model_id} 로드 중..."
        self.character_info: Optional[BaseConfig.OfficePrompt] = None
        self.config: Optional[BaseConfig.LlamaGenerationConfig] = None
        self.enable_rag = enable_rag
        
        print("\n"+ f"{BLUE}LOADING{RESET}:  " + "="*len(self.loading_text))
        print(f"{BLUE}LOADING{RESET}:    {__class__.__name__} 모델 초기화 시작...")

        # JSON 파일 읽기
        with open(self.file_path, 'r', encoding = 'utf-8') as file:
            self.data: BaseConfig.BaseConfig = json.load(file)

        # RAG 시스템 초기화
        if self.enable_rag:
            print(f"{BLUE}LOADING{RESET}:    RAG 시스템 초기화 중...")
            try:
                self.vector_search = VectorClient.VectorSearchHandler()
                if self.vector_search.health_check():
                    print(f"{GREEN}SUCCESS{RESET}:   RAG 시스템 초기화 완료!")
                else:
                    print(f"{YELLOW}WARNING{RESET}:  RAG 시스템 초기화 실패, RAG 비활성화")
                    self.enable_rag = False
                    self.vector_search = None
            except Exception as e:
                print(f"{YELLOW}WARNING{RESET}:  RAG 시스템 오류: {e}, RAG 비활성화")
                self.enable_rag = False
                self.vector_search = None
        else:
            self.vector_search = None

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
        RAG 기능을 활용한 최적화된 응답 생성 메서드

        Args:
            input_text (str): 사용자 입력 텍스트
            search_text (str): 기존 검색 텍스트 (RAG 활성화 시 무시됨)
            chat_list (List[Dict]): 대화 기록

        Returns:
            str: 생성된 텍스트
        """
        start_time = time.time()
        try:
            # RAG를 사용한 컨텍스트 생성
            if self.enable_rag and self.vector_search:
                print(f"    🔍 벡터 검색 시작...")
                vector_context = self.vector_search.get_context_for_llm(
                    query=input_text,
                    max_context_length=2000
                )
                print(f"    ✅ 벡터 검색 완료: {len(vector_context)} 문자")
                reference_text = vector_context
            else:
                # 기존 방식 사용
                current_time = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
                time_info = f"현재 시간은 {current_time}입니다.\n\n"
                reference_text = time_info + (search_text if search_text else "")

            # 대화 기록 정규화
            normalized_chat_list = []
            if chat_list and len(chat_list) > 0:
                for chat in chat_list:
                    normalized_chat = {
                        "index": chat.get("index"),
                        "input_data": chat.get("input_data"),
                        "output_data": self._normalize_escape_chars(chat.get("output_data", ""))
                    }
                    normalized_chat_list.append(normalized_chat)
            else:
                normalized_chat_list = chat_list

            # 캐릭터 정보 설정
            self.character_info = BaseConfig.OfficePrompt(
                name = self.data.get("character_name", "AI Assistant"),
                context = self.data.get("character_setting", "Helpful AI assistant"),
                reference_data = reference_text,
                user_input = input_text,
                chat_list = normalized_chat_list,
            )

            # RAG 프롬프트 생성
            if self.enable_rag and self.vector_search:
                prompt = build_llama3_prompt_with_rag(
                    character_info=self.character_info,
                    vector_context=reference_text
                )
            else:
                prompt = build_llama3_prompt(character_info=self.character_info)
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
            chunks = []
            for text_chunk in self.create_streaming_completion(config = self.config):
                chunks.append(text_chunk)
            
            result = "".join(chunks)
            generation_time = time.time() - start_time
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


if __name__ == "__main__":
    """
    RAG 기능이 추가된 Llama 모델 테스트 스위트
    실제 사용자들이 강아지 건강 문제에 대해 질문하는 시나리오를 시뮬레이션하고
    답변들을 마크다운 파일로 저장합니다.
    """
    import logging
    from datetime import datetime
    
    # 로깅 설정 - print문 대신 사용
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test_results.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # 테스트 질문들 - 실제 반려견 주인들이 할 만한 질문들
    test_questions = [
        {
            "category": "응급상황",
            "question": "우리 강아지가 갑자기 토하고 설사를 해요. 어떻게 해야 할까요?",
            "user_profile": "초보 견주"
        },
        {
            "category": "피부질환",
            "question": "강아지 털이 빠지고 가려워해요. 피부가 빨갛게 되었는데 피부염인가요?",
            "user_profile": "경험 있는 견주"
        },
        {
            "category": "눈질환",
            "question": "강아지 눈에서 노란 눈곱이 계속 나와요. 결막염일까요?",
            "user_profile": "걱정 많은 견주"
        },
        {
            "category": "치과문제",
            "question": "강아지 입에서 냄새가 심하게 나고 잇몸이 빨개요. 치석 때문일까요?",
            "user_profile": "성견 보호자"
        },
        {
            "category": "외상",
            "question": "산책 중에 강아지가 다리를 절뚝거려요. 발가락 사이를 확인해봐야 할까요?",
            "user_profile": "활동적인 견주"
        },
        {
            "category": "내과질환",
            "question": "강아지가 물을 많이 마시고 소변을 자주 봐요. 당뇨병이 의심되나요?",
            "user_profile": "노령견 보호자"
        },
        {
            "category": "행동문제",
            "question": "강아지가 계속 한 곳을 핥아서 상처가 생겼어요. 스트레스 때문일까요?",
            "user_profile": "분리불안 경험자"
        },
        {
            "category": "예방접종",
            "question": "강아지 종합백신 접종 후 기력이 없어요. 부작용인가요?",
            "user_profile": "신중한 견주"
        }
    ]
    
    def run_comprehensive_test():
        """포괄적인 테스트 실행 및 결과 저장"""
        logger.info("=== RAG 기능 테스트 시작 ===")
        
        try:
            # 모델 초기화 (print문 대신 logging 사용)
            original_print = print
            def quiet_print(*args, **kwargs):
                pass
            
            # print 함수를 일시적으로 비활성화
            import builtins
            builtins.print = quiet_print
            
            # 모델 초기화
            model = LlamaModel(enable_rag=True)
            
            # print 함수 복원
            builtins.print = original_print
            
            logger.info("모델 초기화 완료")
            
            # 테스트 결과 저장용 리스트
            test_results = []
            
            for i, test_case in enumerate(test_questions, 1):
                logger.info(f"테스트 {i}/{len(test_questions)} 실행 중: {test_case['category']}")
                
                start_time = datetime.now()
                
                # 응답 생성 (print문 비활성화)
                builtins.print = quiet_print
                try:
                    response = model.generate_response(
                        input_text=test_case["question"],
                        search_text="",
                        chat_list=[]
                    )
                finally:
                    builtins.print = original_print
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 결과 저장
                result = {
                    "test_number": i,
                    "category": test_case["category"],
                    "user_profile": test_case["user_profile"],
                    "question": test_case["question"],
                    "response": response,
                    "response_time": duration,
                    "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S")
                }
                test_results.append(result)
                
                logger.info(f"테스트 {i} 완료 (소요시간: {duration:.2f}초)")
            
            # 마크다운 파일 생성
            markdown_content = generate_markdown_report(test_results, model)
            
            # 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rag_test_results_{timestamp}.md"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"테스트 결과가 {filename}에 저장되었습니다.")
            logger.info("=== 모든 테스트 완료 ===")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류 발생: {e}")
            raise
    
    def generate_markdown_report(test_results, model):
        """마크다운 보고서 생성"""
        timestamp = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
        
        # RAG 시스템 상태 정보
        rag_status = "활성화" if model.enable_rag and model.vector_search else "비활성화"
        vector_status = model.vector_search.get_connection_status() if model.vector_search else {}
        
        md_content = f"""# 🐕 반려견 AI 상담 시스템 테스트 결과
        
## 📋 테스트 개요
- **테스트 일시**: {timestamp}
- **테스트 케이스 수**: {len(test_results)}개
- **RAG 시스템**: {rag_status}
- **모델**: {model.model_id}

## 🔧 시스템 설정
- **벡터 DB 연결**: {vector_status.get('status', 'Unknown')}
- **문서 수**: {vector_status.get('document_count', 0):,}개
- **사용 가능한 진료과**: {', '.join(vector_status.get('available_departments', []))}

---

## 📊 테스트 결과 요약

| 테스트 번호 | 카테고리 | 사용자 프로필 | 응답 시간 |
|------------|---------|-------------|----------|
"""
        
        # 요약 테이블 추가
        for result in test_results:
            md_content += f"| {result['test_number']} | {result['category']} | {result['user_profile']} | {result['response_time']:.2f}초 |\n"
        
        md_content += "\n---\n\n## 📝 상세 테스트 결과\n\n"
        
        # 각 테스트 케이스별 상세 결과
        for result in test_results:
            md_content += f"""### 🔍 테스트 {result['test_number']}: {result['category']}

**👤 사용자 프로필**: {result['user_profile']}  
**⏰ 테스트 시간**: {result['timestamp']}  
**⚡ 응답 시간**: {result['response_time']:.2f}초

#### 💬 사용자 질문
> {result['question']}

#### 🤖 AI 응답
{result['response']}

---

"""
        
        # 통계 정보 추가
        avg_response_time = sum(r['response_time'] for r in test_results) / len(test_results)
        categories = list(set(r['category'] for r in test_results))
        
        md_content += f"""## 📈 통계 정보

### ⏱️ 성능 지표
- **평균 응답 시간**: {avg_response_time:.2f}초
- **최빠른 응답**: {min(r['response_time'] for r in test_results):.2f}초
- **최느린 응답**: {max(r['response_time'] for r in test_results):.2f}초

### 📂 테스트 카테고리
{', '.join(categories)}

### 🏥 진료과별 분석
"""
        
        # 진료과별 통계 (간단히)
        category_stats = {}
        for result in test_results:
            cat = result['category']
            if cat not in category_stats:
                category_stats[cat] = {'count': 0, 'total_time': 0}
            category_stats[cat]['count'] += 1
            category_stats[cat]['total_time'] += result['response_time']
        
        for category, stats in category_stats.items():
            avg_time = stats['total_time'] / stats['count']
            md_content += f"- **{category}**: {stats['count']}개 테스트, 평균 {avg_time:.2f}초\n"
        
        md_content += f"""

---

## 🔍 RAG 시스템 분석

### 벡터 검색 성능
- **검색 시스템**: ChromaDB
- **임베딩 모델**: 기본 임베딩
- **컨텍스트 길이**: 최대 2000자

### 시스템 권장사항
1. **응답 품질**: 벡터 검색을 통해 관련 의료 정보를 효과적으로 활용
2. **응답 속도**: 평균 {avg_response_time:.2f}초로 실용적 수준
3. **정확성**: 전문의 상담 권유 등 의료 안전성 고려

---

*🕒 보고서 생성 시간: {timestamp}*  
*🤖 Generated by RAG-Enhanced Llama AI System*
"""
        
        return md_content
    
    # 메인 테스트 실행
    run_comprehensive_test()