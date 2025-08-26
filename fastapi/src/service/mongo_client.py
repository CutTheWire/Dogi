import os
import uuid
import datetime

from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from domain import ErrorTools

class MongoDBHandler:
    def __init__(self) -> None:
        """
        MongoDBHandler 클래스 초기화.
        MongoDB에 연결하고 필요한 환경 변수를 로드합니다.
        """
        try:
            env_file_path = Path(__file__).resolve().parents[1] / ".env"
            load_dotenv(env_file_path)
            
            # 환경 변수에서 MongoDB 연결 정보 가져오기
            mongo_host = os.getenv("MONGO_HOST")
            mongo_port = os.getenv("MONGO_PORT", "27018")
            mongo_user = os.getenv("MONGO_ADMIN_USER")
            mongo_password = os.getenv("MONGO_ADMIN_PASSWORD")
            mongo_db = os.getenv("MONGO_DATABASE")
            
            # 디버깅 코드 추가
            if not mongo_db:
                raise ValueError("MONGO_DATABASE 환경 변수가 설정되지 않았습니다.")
            
            # MongoDB URI 생성 (authSource를 admin으로 설정)
            self.mongo_uri = (
                f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"
            )
            
            print(f"MongoDB URI: {self.mongo_uri}")  # 디버깅용
            
            # MongoDB 클라이언트 초기화
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[mongo_db]
            
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"MongoDB connection error: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error initializing MongoDBHandler: {str(e)}")

    async def get_db(self) -> List[str]:
        """
        데이터베이스 이름 목록을 반환합니다.
        
        Returns:
            List[str]: 데이터베이스 이름 리스트
        """
        try:
            return await self.client.list_database_names()
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error retrieving database names: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def get_collection(self, database_name: str) -> List[str]:
        """
        데이터베이스의 컬렉션 이름 목록을 반환합니다.
        
        Args:
            database_name (str): 데이터베이스 이름
        
        Returns:
            List[str]: 컬렉션 이름 리스트
        """
        db_names = await self.get_db()
        if (database_name not in db_names):
            raise ErrorTools.NotFoundException(f"Database '{database_name}' not found.")
        try:
            return await self.client[database_name].list_collection_names()
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error retrieving collection names: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

# LLM Session Management Methods ----------------------------------------------------------------------------------
    async def create_llm_session(self, user_id: str) -> str:
        """
        LLM 세션을 생성합니다.
        
        Args:
            user_id (str): 사용자 ID
        
        Returns:
            str: 생성된 세션 ID
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            session_id = str(uuid.uuid4())
            current_time = datetime.datetime.now()
            
            session_document = {
                "session_id": session_id,
                "title": "",  # 첫 메시지로부터 생성됨
                "messages": [],
                "created_at": current_time,
                "updated_at": current_time
            }
            await collection.insert_one(session_document)
            return session_id
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error creating LLM session: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def get_llm_sessions(self, user_id: str) -> List[Dict]:
        """
        사용자의 LLM 세션 목록을 반환합니다.
        
        Args:
            user_id (str): 사용자 ID
        
        Returns:
            List[Dict]: LLM 세션 목록
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            sessions = await collection.find(
                {},
                {
                    "_id": 0,
                    "session_id": 1,
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1
                }
            ).sort("updated_at", -1).to_list(None)
            
            return sessions
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error retrieving LLM sessions: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def get_llm_session(self, user_id: str, session_id: str) -> Dict:
        """
        특정 LLM 세션 정보를 반환합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
        
        Returns:
            Dict: LLM 세션 정보
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one(
                {"session_id": session_id},
                {
                    "_id": 0,
                    "session_id": 1,
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1
                }
            )
            
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
                
            return session
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error retrieving LLM session: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def delete_llm_session(self, user_id: str, session_id: str) -> str:
        """
        LLM 세션을 삭제합니다.

        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
        
        Returns:
            str: 성공 메시지
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            result = await collection.delete_one({"session_id": session_id})
            
            if result.deleted_count == 0:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
                
            return f"Successfully deleted session with ID: {session_id}"
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error deleting LLM session: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def add_llm_message(self,
            user_id: str,
            session_id: str,
            content: str,
            model_id: str,
            answer: str
        ) -> Dict:
        """
        LLM 세션에 메시지를 추가합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
            content (str): 사용자 메시지 내용
            model_id (str): 사용된 모델 ID
            answer (str): AI 응답 내용
        
        Returns:
            Dict: 추가된 메시지 정보
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one({"session_id": session_id})
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
            
            current_time = datetime.datetime.now()
            message_idx = len(session.get("messages", [])) + 1
            
            new_message = {
                "message_idx": str(message_idx),
                "content": content,
                "model_id": model_id,
                "answer": answer,
                "created_at": current_time,
                "updated_at": current_time
            }
            
            # 첫 번째 메시지인 경우 제목 생성
            title_update = {}
            if message_idx == 1:
                title = content[:50] + "..." if len(content) > 50 else content
                title_update["title"] = title
            
            result = await collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": new_message},
                    "$set": {**title_update, "updated_at": current_time}
                }
            )
            
            if result.modified_count == 0:
                raise ErrorTools.InternalServerErrorException("Failed to add message to session")
                
            return new_message
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error adding LLM message: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def get_llm_messages(self, user_id: str, session_id: str) -> List[Dict]:
        """
        LLM 세션의 메시지 목록을 반환합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
        
        Returns:
            List[Dict]: LLM 세션 메시지 목록
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one(
                {"session_id": session_id},
                {"_id": 0, "messages": 1}
            )
            
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
                
            return session.get("messages", [])
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error retrieving LLM messages: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def update_last_llm_message(self,
            user_id: str,
            session_id: str,
            content: str,
            model_id: str,
            answer: str
        ) -> Dict:
        """
        LLM 세션의 마지막 메시지를 수정합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
            content (str): 수정된 메시지 내용
            model_id (str): 사용된 모델 ID
            answer (str): 수정된 AI 응답 내용
        
        Returns:
            Dict: 수정된 메시지 정보
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one({"session_id": session_id})
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
            
            messages = session.get("messages", [])
            if not messages:
                raise ErrorTools.NotFoundException(f"No messages found in session: {session_id}")
            
            current_time = datetime.datetime.now()
            last_message_idx = len(messages) - 1
            
            # 마지막 메시지 업데이트
            updated_message = {
                "message_idx": messages[last_message_idx]["message_idx"],
                "content": content,
                "model_id": model_id,
                "answer": answer,
                "created_at": messages[last_message_idx]["created_at"],
                "updated_at": current_time
            }
            
            result = await collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        f"messages.{last_message_idx}": updated_message,
                        "updated_at": current_time
                    }
                }
            )
            
            if result.modified_count == 0:
                raise ErrorTools.InternalServerErrorException("Failed to update last message")
                
            return updated_message
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error updating LLM message: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def delete_last_llm_message(self, user_id: str, session_id: str) -> str:
        """
        LLM 세션의 마지막 메시지를 삭제합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
        
        Returns:
            str: 성공 메시지
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one({"session_id": session_id})
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
            
            messages = session.get("messages", [])
            if not messages:
                raise ErrorTools.NotFoundException(f"No messages found in session: {session_id}")
            
            current_time = datetime.datetime.now()
            
            result = await collection.update_one(
                {"session_id": session_id},
                {
                    "$pop": {"messages": 1},
                    "$set": {"updated_at": current_time}
                }
            )
            
            if result.modified_count == 0:
                raise ErrorTools.InternalServerErrorException("Failed to delete last message")
                
            return f"Successfully deleted last message from session: {session_id}"
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error deleting LLM message: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")

    async def regenerate_last_llm_message(self,
            user_id: str,
            session_id: str,
            model_id: str,
            answer: str
        ) -> Dict:
        """
        LLM 세션의 마지막 메시지를 재생성합니다.
        
        Args:
            user_id (str): 사용자 ID
            session_id (str): 세션 ID
            model_id (str): 사용된 모델 ID
            answer (str): 새로운 AI 응답 내용
        
        Returns:
            Dict: 재생성된 메시지 정보
        """
        try:
            collection_name = f'llm_sessions_{user_id}'
            collection = self.db[collection_name]
            
            session = await collection.find_one({"session_id": session_id})
            if session is None:
                raise ErrorTools.NotFoundException(f"Session not found with ID: {session_id}")
            
            messages = session.get("messages", [])
            if not messages:
                raise ErrorTools.NotFoundException(f"No messages found in session: {session_id}")
            
            current_time = datetime.datetime.now()
            last_message_idx = len(messages) - 1
            last_message = messages[last_message_idx]
            
            # 마지막 메시지의 답변만 업데이트
            regenerated_message = {
                "message_idx": last_message["message_idx"],
                "content": last_message["content"],
                "model_id": model_id,
                "answer": answer,
                "created_at": last_message["created_at"],
                "updated_at": current_time
            }
            
            result = await collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        f"messages.{last_message_idx}": regenerated_message,
                        "updated_at": current_time
                    }
                }
            )
            
            if result.modified_count == 0:
                raise ErrorTools.InternalServerErrorException("Failed to regenerate last message")
                
            return regenerated_message
        except PyMongoError as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Error regenerating LLM message: {str(e)}")
        except Exception as e:
            raise ErrorTools.InternalServerErrorException(detail=f"Unexpected error: {str(e)}")
