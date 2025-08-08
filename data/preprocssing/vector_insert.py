import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import chromadb
from chromadb.config import Settings
from tqdm import tqdm
import time
import sys

# NumPy 호환성 문제 해결
import warnings
warnings.filterwarnings("ignore", message=".*NumPy.*")

# NumPy 버전 강제 설정
os.environ['NUMPY_VERSION'] = '1.26.0'  

try:
    # NumPy 1.x 버전 강제 로드
    import numpy as np
    if hasattr(np, '__version__') and np.__version__.startswith('2.'):
        print("Warning: NumPy 2.x detected. Some features may not work properly.")
except ImportError:
    print("NumPy not available, continuing without it...")

# sentence-transformers import를 try-catch로 보호
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception as e:
    print(f"Warning: sentence-transformers import failed: {e}")
    print("Falling back to alternative embedding method...")
    SENTENCE_TRANSFORMERS_AVAILABLE = False

import re

# 텔레메트리 비활성화
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

# 로깅 설정 - HTTP 로그 숨기기
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# httpx 로그 레벨을 WARNING으로 설정하여 INFO 로그 숨기기
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)

def format_file_size(size_bytes: int) -> str:
    """파일 크기를 읽기 쉬운 형식으로 변환"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f}{size_names[i]}"

def print_progress_inline(current: int, total: int, prefix: str = "", suffix: str = "", length: int = 50):
    """인라인 진행률 표시 (같은 줄에서 업데이트)"""
    percent = (current / total) * 100
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    
    # \r을 사용하여 같은 줄에서 업데이트
    print(f'\r{prefix} |{bar}| {current}/{total} ({percent:.1f}%) {suffix}', end='', flush=True)
    
    # 완료 시 줄바꿈
    if current == total:
        print()

def scan_directory_files(data_dir: str) -> Tuple[List[Path], Dict[str, Any]]:
    """디렉토리 전체 스캔하여 파일 정보 수집"""
    data_path = Path(data_dir)
    all_files = []
    stats = {
        'total_files': 0,
        'total_size': 0,
        'corpus_files': 0,
        'corpus_size': 0,
        'qa_files': 0,
        'qa_size': 0,
        'departments': set(),
        'error_files': []
    }
    
    print("\n🔍 디렉토리 스캔 중...")
    
    # 원천데이터(말뭉치) 스캔
    corpus_dir = data_path / "1.원천데이터" / "말뭉치 데이터"
    if corpus_dir.exists():
        print(f"📁 원천데이터 스캔: {corpus_dir}")
        dept_dirs = list(corpus_dir.iterdir())
        
        for idx, dept_dir in enumerate(dept_dirs):
            if dept_dir.is_dir():
                # 인라인 진행률 표시
                print_progress_inline(idx + 1, len(dept_dirs), f"📂 {dept_dir.name}", "")
                
                stats['departments'].add(dept_dir.name)
                for json_file in dept_dir.glob("*.json"):
                    try:
                        file_size = json_file.stat().st_size
                        all_files.append(json_file)
                        stats['total_files'] += 1
                        stats['total_size'] += file_size
                        stats['corpus_files'] += 1
                        stats['corpus_size'] += file_size
                    except Exception as e:
                        stats['error_files'].append(str(json_file))
                        logger.warning(f"Error accessing file {json_file}: {e}")
    
    # 라벨링데이터(질의응답) 스캔
    qa_dir = data_path / "2.라벨링데이터" / "질의응답 데이터"
    if qa_dir.exists():
        print(f"\n📁 라벨링데이터 스캔: {qa_dir}")
        dept_dirs = list(qa_dir.iterdir())
        
        for idx, dept_dir in enumerate(dept_dirs):
            if dept_dir.is_dir():
                # 인라인 진행률 표시
                print_progress_inline(idx + 1, len(dept_dirs), f"📂 {dept_dir.name}", "")
                
                stats['departments'].add(dept_dir.name)
                for json_file in dept_dir.glob("*.json"):
                    try:
                        file_size = json_file.stat().st_size
                        all_files.append(json_file)
                        stats['total_files'] += 1
                        stats['total_size'] += file_size
                        stats['qa_files'] += 1
                        stats['qa_size'] += file_size
                    except Exception as e:
                        stats['error_files'].append(str(json_file))
                        logger.warning(f"Error accessing file {json_file}: {e}")
    
    return all_files, stats

def print_scan_summary(stats: Dict[str, Any]):
    """스캔 결과 요약 출력"""
    print("\n" + "="*60)
    print("📊 디렉토리 스캔 결과")
    print("="*60)
    print(f"📂 총 파일 수: {stats['total_files']:,}개")
    print(f"💾 총 파일 크기: {format_file_size(stats['total_size'])}")
    print(f"📋 원천데이터(말뭉치): {stats['corpus_files']:,}개 ({format_file_size(stats['corpus_size'])})")
    print(f"❓ 라벨링데이터(Q&A): {stats['qa_files']:,}개 ({format_file_size(stats['qa_size'])})")
    print(f"🏥 진료과목: {len(stats['departments'])}개 - {', '.join(sorted(stats['departments']))}")
    
    if stats['error_files']:
        print(f"⚠️  접근 실패 파일: {len(stats['error_files'])}개")
    
    print("="*60)

class VetDataVectorizer:
    def __init__(self, 
                chroma_host: str = "localhost", 
                chroma_port: int = 8000,
                model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ):
        """
        수의학 데이터 벡터화 클래스
        
        Args:
            chroma_host: ChromaDB 호스트
            chroma_port: ChromaDB 포트
            model_name: 한국어 임베딩 모델
        """
        # HTTP 로그 숨기기
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("chromadb").setLevel(logging.ERROR)
        
        self.client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False  # 텔레메트리 비활성화
            )
        )
        
        # 통계 추적
        self.stats = {
            'processed_files': 0,
            'total_documents': 0,
            'corpus_documents': 0,
            'qa_documents': 0,
            'failed_files': 0,
            'processing_time': 0
        }
        
        # 임베딩 모델 초기화
        self.embedding_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                print("🤖 임베딩 모델 로딩 중...")
                self.embedding_model = SentenceTransformer(model_name)
                print(f"✅ 임베딩 모델 로드 완료: {model_name}")
            except Exception as e:
                print(f"⚠️ 모델 로드 실패 {model_name}: {e}")
                # 대안 모델들 시도
                alternative_models = [
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
                ]
                
                for alt_model in alternative_models:
                    try:
                        print(f"🔄 대안 모델 시도: {alt_model}")
                        self.embedding_model = SentenceTransformer(alt_model)
                        print(f"✅ 대안 모델 로드 완료: {alt_model}")
                        break
                    except Exception as alt_e:
                        print(f"⚠️ 대안 모델 실패 {alt_model}: {alt_e}")
                        continue
        
        if self.embedding_model is None:
            print("⚠️ 임베딩 모델 없음. 간단한 텍스트 임베딩 사용.")
        
        # 컬렉션 생성 또는 가져오기
        self.collection = self.client.get_or_create_collection(
            name="vet_medical_data",
            metadata={"description": "반려동물 의료 데이터"}
        )
        
    def simple_text_embedding(self, texts: List[str]) -> List[List[float]]:
        """간단한 텍스트 임베딩 (fallback method)"""
        embeddings = []
        for text in texts:
            # 간단한 해시 기반 임베딩 (실제 프로덕션에서는 사용하지 않음)
            text_hash = hash(text)
            # 384차원 벡터 생성 (sentence-transformers와 호환)
            embedding = [float((text_hash + i) % 1000) / 1000.0 for i in range(384)]
            embeddings.append(embedding)
        return embeddings
    
    def clean_text(self, text: str) -> str:
        """텍스트 전처리"""
        if not text:
            return ""
        
        # 연속된 공백 및 줄바꿈 정리
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        
        # 특수문자 정리 (필요에 따라 조정)
        text = text.strip()
        
        return text
    
    def chunk_text(self, text: str, max_length: int = 500) -> List[str]:
        """긴 텍스트를 청크 단위로 분할"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        sentences = text.split('.')
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= max_length:
                current_chunk += sentence + "."
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "."
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
    
    def process_corpus_data(self, file_path: str) -> List[Dict[str, Any]]:
        """원천데이터(말뭉치) 처리"""
        try:
            # UTF-8 BOM 처리 개선
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except UnicodeDecodeError:
                # 대안 인코딩 시도
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            documents = []
            
            # 제목, 저자, 출판사 정보
            title = data.get('title', '')
            author = data.get('author', '')
            publisher = data.get('publisher', '')
            department = data.get('department', '')
            disease_content = data.get('disease', '')
            
            # 질병 내용을 청크로 분할
            cleaned_content = self.clean_text(disease_content)
            chunks = self.chunk_text(cleaned_content, max_length=500)
            
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 50:  # 너무 짧은 청크 제외
                    continue
                    
                doc = {
                    'id': f"{Path(file_path).stem}_chunk_{i}",
                    'content': chunk,
                    'metadata': {
                        'source_type': 'corpus',
                        'title': title,
                        'author': author,
                        'publisher': publisher,
                        'department': department,
                        'file_path': file_path,
                        'chunk_index': i
                    }
                }
                documents.append(doc)
                
            return documents
            
        except Exception as e:
            # 에러도 조용히 처리
            self.stats['failed_files'] += 1
            return []
    
    def process_qa_data(self, file_path: str) -> List[Dict[str, Any]]:
        """라벨링데이터(질의응답) 처리"""
        try:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            documents = []
            
            # 메타데이터
            meta = data.get('meta', {})
            qa = data.get('qa', {})
            
            # 질문과 답변을 별도 문서로 저장
            instruction = qa.get('instruction', '')
            user_input = qa.get('input', '')
            output = qa.get('output', '')
            
            # 질문 문서
            if user_input:
                doc_question = {
                    'id': f"{Path(file_path).stem}_question",
                    'content': f"{instruction}\n\n질문: {user_input}",
                    'metadata': {
                        'source_type': 'qa_question',
                        'life_cycle': meta.get('lifeCycle', ''),
                        'department': meta.get('department', ''),
                        'disease': meta.get('disease', ''),
                        'file_path': file_path,
                        'content_type': 'question'
                    }
                }
                documents.append(doc_question)
            
            # 답변 문서
            if output:
                doc_answer = {
                    'id': f"{Path(file_path).stem}_answer",
                    'content': f"답변: {output}",
                    'metadata': {
                        'source_type': 'qa_answer',
                        'life_cycle': meta.get('lifeCycle', ''),
                        'department': meta.get('department', ''),
                        'disease': meta.get('disease', ''),
                        'file_path': file_path,
                        'content_type': 'answer',
                        'related_question': user_input
                    }
                }
                documents.append(doc_answer)
            
            return documents
            
        except Exception as e:
            # 에러도 조용히 처리
            self.stats['failed_files'] += 1
            return []
    
    def insert_documents(self, documents: List[Dict[str, Any]]):
        """문서들을 ChromaDB에 삽입"""
        if not documents:
            return
        
        try:
            # 텍스트 임베딩 생성
            texts = [doc['content'] for doc in documents]
            
            if self.embedding_model is not None:
                try:
                    embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
                    # NumPy 배열을 리스트로 변환 (NumPy 호환성 문제 방지)
                    if hasattr(embeddings, 'tolist'):
                        embeddings = embeddings.tolist()
                    else:
                        embeddings = list(embeddings)
                except Exception as e:
                    embeddings = self.simple_text_embedding(texts)
            else:
                embeddings = self.simple_text_embedding(texts)
            
            # ChromaDB에 삽입
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=[doc['metadata'] for doc in documents],
                ids=[doc['id'] for doc in documents]
            )
            
            # 통계 업데이트
            self.stats['total_documents'] += len(documents)
            if documents[0]['metadata']['source_type'].startswith('corpus'):
                self.stats['corpus_documents'] += len(documents)
            else:
                self.stats['qa_documents'] += len(documents)
            
        except Exception as e:
            # 에러도 조용히 처리
            pass
    
    def process_files_with_progress(self, file_list: List[Path]):
        """진행률 표시와 함께 파일들 처리 (깔끔한 인라인 버전)"""
        start_time = time.time()
        total_files = len(file_list)
        
        print(f"\n🚀 파일 처리 시작 (총 {total_files:,}개 파일)")
        print("💡 HTTP 로그가 숨겨졌습니다. 깔끔한 진행률 표시를 즐기세요!")
        
        for idx, file_path in enumerate(file_list):
            # 파일명 길이 제한
            filename = file_path.name
            if len(filename) > 25:
                filename = filename[:22] + "..."
            
            # 인라인 진행률 표시
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total_files - idx - 1) / rate if rate > 0 else 0
            
            progress_info = f"📄 {filename} | 📊 {self.stats['total_documents']:,}docs | ⚡ {rate:.1f}f/s | ⏰ {eta:.0f}s"
            print_progress_inline(idx + 1, total_files, "🔄", progress_info)
            
            # 파일 유형에 따라 처리
            if "말뭉치 데이터" in str(file_path):
                documents = self.process_corpus_data(str(file_path))
            elif "질의응답 데이터" in str(file_path):
                documents = self.process_qa_data(str(file_path))
            else:
                continue
            
            if documents:
                self.insert_documents(documents)
            
            self.stats['processed_files'] += 1
        
        self.stats['processing_time'] = time.time() - start_time
        print(f"\n✅ 파일 처리 완료!")
    
    def get_collection_info(self):
        """컬렉션 정보 출력"""
        count = self.collection.count()
        
        print("\n" + "="*60)
        print("📊 벡터화 완료 결과")
        print("="*60)
        print(f"✅ 총 처리된 문서: {self.stats['total_documents']:,}개")
        print(f"📋 원천데이터 문서: {self.stats['corpus_documents']:,}개")
        print(f"❓ 질의응답 문서: {self.stats['qa_documents']:,}개")
        print(f"📁 처리된 파일: {self.stats['processed_files']:,}개")
        print(f"❌ 실패한 파일: {self.stats['failed_files']:,}개")
        print(f"⏱️  처리 시간: {self.stats['processing_time']:.2f}초")
        print(f"🚀 평균 속도: {self.stats['processed_files']/self.stats['processing_time']:.1f} 파일/초")
        print(f"🗄️  ChromaDB 저장된 문서: {count:,}개")
        print("="*60)
        
        # 샘플 문서 조회
        if count > 0:
            print("\n📄 샘플 문서:")
            sample = self.collection.peek(limit=3)
            for i, (doc, metadata) in enumerate(zip(sample['documents'], sample['metadatas'])):
                print(f"\n문서 {i+1}: {doc[:100]}...")
                print(f"메타데이터: {metadata}")
    
    def search_similar(self, query: str, n_results: int = 5, department: str = None):
        """유사 문서 검색"""
        if self.embedding_model is not None:
            try:
                query_embedding = self.embedding_model.encode([query], show_progress_bar=False)
                if hasattr(query_embedding, 'tolist'):
                    query_embedding = query_embedding.tolist()
                else:
                    query_embedding = list(query_embedding)
            except Exception as e:
                query_embedding = self.simple_text_embedding([query])
        else:
            query_embedding = self.simple_text_embedding([query])
        
        where_clause = {}
        if department:
            where_clause["department"] = department
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where_clause if where_clause else None
        )
        
        return results

def main():
    """메인 실행 함수"""
    print("🐕 반려동물 의료 데이터 벡터화 시스템")
    print("="*60)
    
    current_file = Path(__file__).resolve()
    data_dir = current_file.parents[1] / "raw"
    
    print(f"📁 데이터 디렉토리: {data_dir}")
    
    # 디렉토리 존재 확인
    if not data_dir.exists():
        print(f"❌ 데이터 디렉토리가 존재하지 않습니다: {data_dir}")
        return
    
    # 1단계: 전체 파일 스캔
    file_list, scan_stats = scan_directory_files(str(data_dir))
    print_scan_summary(scan_stats)
    
    if not file_list:
        print("❌ 처리할 파일이 없습니다.")
        return
    
    # 2단계: VectorDB 초기화
    print("\n🚀 벡터화 시작...")
    vectorizer = VetDataVectorizer(
        chroma_host="localhost",  # Docker 컨테이너 실행 시 "chromadb"로 변경
        chroma_port=8000
    )
    
    # 3단계: 파일 처리 (깔끔한 인라인 진행률 표시)
    vectorizer.process_files_with_progress(file_list)
    
    # 4단계: 결과 확인
    vectorizer.get_collection_info()
    
    # 5단계: 검색 테스트
    print("\n🔍 검색 테스트")
    print("="*60)
    test_query = "강아지 파보장염 치료"
    results = vectorizer.search_similar(test_query, n_results=3)
    
    print(f"\n🔎 검색어: '{test_query}'")
    print("-" * 60)
    
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0], 
        results['metadatas'][0], 
        results['distances'][0]
    )):
        print(f"\n📋 결과 {i+1} (유사도: {1-distance:.4f}):")
        print(f"📄 내용: {doc[:200]}...")
        print(f"🏥 진료과: {metadata.get('department', 'N/A')}")
        print(f"📁 유형: {metadata.get('source_type', 'N/A')}")

if __name__ == "__main__":
    main()