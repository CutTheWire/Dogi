import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
import time
import sys

# 텔레메트리 비활성화
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self, 
                chroma_host: str = "localhost", 
                chroma_port: int = 7999):
        """
        벡터 데이터베이스 관리 클래스
        
        Args:
            chroma_host: ChromaDB 호스트
            chroma_port: ChromaDB 포트
        """
        try:
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(
                    allow_reset=True,
                    anonymized_telemetry=False
                )
            )
            print(f"✅ ChromaDB 연결 성공: {chroma_host}:{chroma_port}")
        except Exception as e:
            print(f"❌ ChromaDB 연결 실패: {e}")
            print(f"🔍 ChromaDB가 실행 중인지 확인하세요:")
            print(f"   - docker compose up -d chromadb")
            print(f"   - http://localhost:{chroma_port}")
            sys.exit(1)
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """모든 컬렉션 목록 조회"""
        try:
            collections = self.client.list_collections()
            collection_info = []
            
            for collection in collections:
                try:
                    # 컬렉션 정보 수집
                    count = collection.count()
                    metadata = collection.metadata
                    
                    info = {
                        'name': collection.name,
                        'count': count,
                        'metadata': metadata
                    }
                    collection_info.append(info)
                except Exception as e:
                    logger.warning(f"Error getting info for collection {collection.name}: {e}")
                    collection_info.append({
                        'name': collection.name,
                        'count': 'unknown',
                        'metadata': {}
                    })
            
            return collection_info
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """특정 컬렉션 삭제"""
        try:
            self.client.delete_collection(name=collection_name)
            print(f"✅ 컬렉션 '{collection_name}' 삭제 완료")
            return True
        except Exception as e:
            print(f"❌ 컬렉션 '{collection_name}' 삭제 실패: {e}")
            return False
    
    def reset_database(self) -> bool:
        """전체 데이터베이스 초기화 (Reset이 비활성화된 경우 개별 삭제)"""
        try:
            # 먼저 Reset 시도
            self.client.reset()
            print("✅ ChromaDB 전체 초기화 완료")
            return True
        except Exception as e:
            if "Reset is disabled" in str(e):
                print("⚠️  Reset이 비활성화되어 있습니다. 개별 컬렉션 삭제로 진행합니다...")
                return self.delete_all_collections()
            else:
                print(f"❌ ChromaDB 초기화 실패: {e}")
                return False
    
    def delete_all_collections(self) -> bool:
        """모든 컬렉션을 개별적으로 삭제"""
        try:
            collections = self.client.list_collections()
            if not collections:
                print("✅ 삭제할 컬렉션이 없습니다.")
                return True
            
            success_count = 0
            total_count = len(collections)
            
            print(f"🗑️  {total_count}개 컬렉션을 개별 삭제 중...")
            
            for i, collection in enumerate(collections, 1):
                collection_name = collection.name
                print(f"🔄 ({i}/{total_count}) '{collection_name}' 삭제 중...")
                
                try:
                    self.client.delete_collection(name=collection_name)
                    print(f"   ✅ '{collection_name}' 삭제 완료")
                    success_count += 1
                except Exception as e:
                    print(f"   ❌ '{collection_name}' 삭제 실패: {e}")
            
            if success_count == total_count:
                print(f"✅ 모든 컬렉션 삭제 완료! ({success_count}/{total_count})")
                return True
            else:
                print(f"⚠️  일부 컬렉션 삭제 실패 ({success_count}/{total_count})")
                return False
                
        except Exception as e:
            print(f"❌ 컬렉션 삭제 실패: {e}")
            return False
    
    def clear_collection(self, collection_name: str) -> bool:
        """컬렉션의 모든 데이터 삭제 (컬렉션은 유지)"""
        try:
            collection = self.client.get_collection(name=collection_name)
            
            # 모든 문서 ID 조회
            all_data = collection.get()
            if not all_data['ids']:
                print(f"✅ 컬렉션 '{collection_name}'이 이미 비어있습니다.")
                return True
            
            # 배치로 삭제 (한 번에 많은 데이터 삭제 시 성능 개선)
            batch_size = 1000
            ids = all_data['ids']
            total_ids = len(ids)
            
            print(f"🗑️  '{collection_name}'에서 {total_ids:,}개 문서 삭제 중...")
            
            for i in range(0, total_ids, batch_size):
                batch_ids = ids[i:i + batch_size]
                collection.delete(ids=batch_ids)
                
                progress = min(i + batch_size, total_ids)
                print(f"   🔄 진행률: {progress:,}/{total_ids:,} ({progress/total_ids*100:.1f}%)")
            
            # 삭제 확인
            final_count = collection.count()
            if final_count == 0:
                print(f"✅ 컬렉션 '{collection_name}' 데이터 삭제 완료!")
                return True
            else:
                print(f"⚠️  일부 데이터가 남아있습니다: {final_count:,}개")
                return False
                
        except Exception as e:
            print(f"❌ 컬렉션 '{collection_name}' 데이터 삭제 실패: {e}")
            return False
    
    def get_collection_details(self, collection_name: str) -> Dict[str, Any]:
        """컬렉션 상세 정보 조회"""
        try:
            collection = self.client.get_collection(name=collection_name)
            
            # 기본 정보
            count = collection.count()
            metadata = collection.metadata
            
            # 샘플 데이터 조회
            sample_data = {}
            if count > 0:
                try:
                    sample = collection.peek(limit=3)
                    sample_data = {
                        'documents': sample.get('documents', []),
                        'metadatas': sample.get('metadatas', []),
                        'ids': sample.get('ids', [])
                    }
                except Exception as e:
                    logger.warning(f"Error getting sample data: {e}")
            
            return {
                'name': collection_name,
                'count': count,
                'metadata': metadata,
                'sample_data': sample_data
            }
        except Exception as e:
            logger.error(f"Error getting collection details: {e}")
            return {}
    
    def print_collection_summary(self, collections: List[Dict[str, Any]]):
        """컬렉션 요약 정보 출력"""
        if not collections:
            print("📭 컬렉션이 없습니다.")
            return
        
        print("\n" + "="*70)
        print("📊 ChromaDB 컬렉션 현황")
        print("="*70)
        
        total_documents = 0
        for i, collection in enumerate(collections, 1):
            count = collection['count']
            if isinstance(count, int):
                total_documents += count
            
            print(f"📂 {i}. {collection['name']}")
            print(f"   📄 문서 수: {count:,}개" if isinstance(count, int) else f"   📄 문서 수: {count}")
            if collection['metadata']:
                print(f"   📋 메타데이터: {collection['metadata']}")
            print()
        
        print(f"📈 총 문서 수: {total_documents:,}개")
        print("="*70)

def print_menu():
    """메뉴 출력"""
    print("\n" + "="*50)
    print("🗂️  ChromaDB 벡터 데이터베이스 관리 도구")
    print("="*50)
    print("1. 📋 컬렉션 목록 조회")
    print("2. 🔍 컬렉션 상세 정보 조회")
    print("3. 🗑️  특정 컬렉션 삭제")
    print("4. 🧹 컬렉션 데이터 비우기")
    print("5. 💥 전체 데이터베이스 초기화")
    print("6. 🔄 새로고침")
    print("0. 🚪 종료")
    print("="*50)

def confirm_action(message: str) -> bool:
    """사용자 확인"""
    while True:
        response = input(f"\n⚠️  {message} (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("'y' 또는 'n'을 입력하세요.")

def main():
    """메인 실행 함수"""
    print("🐕 반려동물 의료 데이터 벡터 DB 관리 도구")
    
    # VectorDB 매니저 초기화
    try:
        db_manager = VectorDBManager(
            chroma_host="localhost",
            chroma_port=7999
        )
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return
    
    # 초기 컬렉션 목록 조회
    collections = db_manager.list_collections()
    db_manager.print_collection_summary(collections)
    
    while True:
        print_menu()
        choice = input("\n선택하세요: ").strip()
        
        if choice == "1":
            # 컬렉션 목록 조회
            print("\n🔄 컬렉션 목록 조회 중...")
            collections = db_manager.list_collections()
            db_manager.print_collection_summary(collections)
        
        elif choice == "2":
            # 컬렉션 상세 정보 조회
            collections = db_manager.list_collections()
            if not collections:
                print("📭 조회할 컬렉션이 없습니다.")
                continue
            
            print("\n📋 사용 가능한 컬렉션:")
            for i, collection in enumerate(collections, 1):
                print(f"{i}. {collection['name']}")
            
            try:
                idx = int(input("\n조회할 컬렉션 번호: ")) - 1
                if 0 <= idx < len(collections):
                    collection_name = collections[idx]['name']
                    print(f"\n🔍 '{collection_name}' 상세 정보 조회 중...")
                    
                    details = db_manager.get_collection_details(collection_name)
                    if details:
                        print("\n" + "="*60)
                        print(f"📂 컬렉션: {details['name']}")
                        print("="*60)
                        print(f"📄 문서 수: {details['count']:,}개")
                        print(f"📋 메타데이터: {details['metadata']}")
                        
                        if details['sample_data']['documents']:
                            print("\n📝 샘플 문서:")
                            for i, (doc, meta, doc_id) in enumerate(zip(
                                details['sample_data']['documents'][:3],
                                details['sample_data']['metadatas'][:3],
                                details['sample_data']['ids'][:3]
                            )):
                                print(f"\n문서 {i+1} (ID: {doc_id}):")
                                print(f"내용: {doc[:150]}...")
                                print(f"메타: {meta}")
                        print("="*60)
                else:
                    print("❌ 잘못된 번호입니다.")
            except ValueError:
                print("❌ 숫자를 입력하세요.")
        
        elif choice == "3":
            # 특정 컬렉션 삭제
            collections = db_manager.list_collections()
            if not collections:
                print("📭 삭제할 컬렉션이 없습니다.")
                continue
            
            print("\n📋 사용 가능한 컬렉션:")
            for i, collection in enumerate(collections, 1):
                count = collection['count']
                print(f"{i}. {collection['name']} ({count:,}개 문서)" if isinstance(count, int) else f"{i}. {collection['name']} ({count} 문서)")
            
            try:
                idx = int(input("\n삭제할 컬렉션 번호: ")) - 1
                if 0 <= idx < len(collections):
                    collection_name = collections[idx]['name']
                    
                    if confirm_action(f"'{collection_name}' 컬렉션을 삭제하시겠습니까?"):
                        if db_manager.delete_collection(collection_name):
                            print(f"✅ '{collection_name}' 삭제 완료!")
                            # 목록 새로고침
                            collections = db_manager.list_collections()
                            db_manager.print_collection_summary(collections)
                    else:
                        print("❌ 삭제가 취소되었습니다.")
                else:
                    print("❌ 잘못된 번호입니다.")
            except ValueError:
                print("❌ 숫자를 입력하세요.")
        
        elif choice == "4":
            # 컬렉션 데이터 비우기
            collections = db_manager.list_collections()
            if not collections:
                print("📭 비울 컬렉션이 없습니다.")
                continue
            
            print("\n📋 사용 가능한 컬렉션:")
            for i, collection in enumerate(collections, 1):
                count = collection['count']
                print(f"{i}. {collection['name']} ({count:,}개 문서)" if isinstance(count, int) else f"{i}. {collection['name']} ({count} 문서)")
            
            try:
                idx = int(input("\n비울 컬렉션 번호: ")) - 1
                if 0 <= idx < len(collections):
                    collection_name = collections[idx]['name']
                    count = collections[idx]['count']
                    
                    if confirm_action(f"'{collection_name}' 컬렉션의 {count:,}개 문서를 모두 삭제하시겠습니까?"):
                        if db_manager.clear_collection(collection_name):
                            print(f"✅ '{collection_name}' 데이터 삭제 완료!")
                            # 목록 새로고침
                            collections = db_manager.list_collections()
                            db_manager.print_collection_summary(collections)
                    else:
                        print("❌ 삭제가 취소되었습니다.")
                else:
                    print("❌ 잘못된 번호입니다.")
            except ValueError:
                print("❌ 숫자를 입력하세요.")
        
        elif choice == "5":
            # 전체 데이터베이스 초기화
            collections = db_manager.list_collections()
            total_docs = sum(c['count'] for c in collections if isinstance(c['count'], int))
            
            print(f"\n⚠️  전체 데이터베이스 초기화")
            print(f"📂 컬렉션 수: {len(collections)}개")
            print(f"📄 총 문서 수: {total_docs:,}개")
            
            if confirm_action("모든 데이터를 삭제하시겠습니까? (복구 불가능)"):
                if db_manager.reset_database():
                    print("✅ 전체 데이터베이스 초기화 완료!")
                    # 목록 새로고침
                    collections = db_manager.list_collections()
                    db_manager.print_collection_summary(collections)
            else:
                print("❌ 초기화가 취소되었습니다.")
        
        elif choice == "6":
            # 새로고침
            print("\n🔄 새로고침 중...")
            collections = db_manager.list_collections()
            db_manager.print_collection_summary(collections)
        
        elif choice == "0":
            # 종료
            print("\n👋 프로그램을 종료합니다.")
            break
        
        else:
            print("❌ 잘못된 선택입니다. 다시 선택하세요.")
        
        # 계속하려면 엔터
        input("\n계속하려면 Enter를 누르세요...")

if __name__ == "__main__":
    main()