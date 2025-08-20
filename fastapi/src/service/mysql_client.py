import os
import aiomysql
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from datetime import datetime

class MongoDBHandler:
    """
    MySQL 데이터베이스 핸들러
    MySQL 데이터베이스와의 연결 및 쿼리 실행을 관리합니다.
    """
    
    def __init__(self):
        env_file_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(env_file_path)
        
        self.host = os.getenv('MYSQL_HOST')
        self.port = int(os.getenv('MYSQL_PORT'))
        self.database = os.getenv('MYSQL_DATABASE')
        self.user = os.getenv('MYSQL_USER')
        self.password = os.getenv('MYSQL_PASSWORD')
        self.pool = None
        
    async def initialize(self):
        """
        MySQL 연결 풀 초기화
        """
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                charset='utf8mb4',
                autocommit=True,
                minsize=5,
                maxsize=20
            )
            print("INFO:     MySQL 연결 풀이 성공적으로 초기화되었습니다.")
        except Exception as e:
            print(f"ERROR:    MySQL 초기화 오류: {e}")
            raise e
    
    async def close(self):
        """
        MySQL 연결 풀 종료
        """
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            print("INFO:     MySQL 연결이 종료되었습니다.")
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        새로운 사용자 생성
        
        Args:
            user_data (Dict[str, Any]): 사용자 정보 딕셔너리
        
        Returns:
            Dict[str, Any]: 생성된 사용자 정보
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # 중복 확인
                    await cursor.execute(
                        "SELECT id FROM users WHERE user_id = %s OR email = %s",
                        (user_data['user_id'], user_data['email'])
                    )
                    existing_user = await cursor.fetchone()
                    
                    if existing_user:
                        raise ValueError("이미 존재하는 사용자 ID 또는 이메일입니다.")
                    
                    # 사용자 생성
                    await cursor.execute("""
                        INSERT INTO users (user_id, email, password_hash, full_name, is_active, is_verified)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_data['user_id'],
                        user_data['email'],
                        user_data['password_hash'],
                        user_data['full_name'],
                        user_data.get('is_active', True),
                        user_data.get('is_verified', False)
                    ))
                    
                    # 생성된 사용자 조회
                    await cursor.execute(
                        "SELECT * FROM users WHERE user_id = %s",
                        (user_data['user_id'],)
                    )
                    user = await cursor.fetchone()
                    
                    # 프로필 테이블에도 기본 레코드 생성
                    await cursor.execute("""
                        INSERT INTO user_profiles (user_id, phone, birth_date, gender)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        user_data['user_id'],
                        user_data.get('phone'),
                        user_data.get('birth_date'),
                        user_data.get('gender')
                    ))
                    
                    return user
                    
                except Exception as e:
                    await connection.rollback()
                    raise e
    
    async def get_user_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 사용자 조회
        
        Args:
            user_id (str): 사용자 ID

        Returns:
            Optional[Dict[str, Any]]: 사용자 정보 딕셔너리, 존재하지
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT u.*, p.phone, p.birth_date, p.gender, p.profile_image_url, p.bio
                    FROM users u
                    LEFT JOIN user_profiles p ON u.user_id = p.user_id
                    WHERE u.user_id = %s AND u.is_active = TRUE
                """, (user_id,))
                return await cursor.fetchone()
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        이메일로 사용자 조회
        
        Args:
            email (str): 사용자 이메일
        
        Returns:
            Optional[Dict[str, Any]]: 사용자 정보 딕셔너리, 존재하지 않으면 None
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT u.*, p.phone, p.birth_date, p.gender, p.profile_image_url, p.bio
                    FROM users u
                    LEFT JOIN user_profiles p ON u.user_id = p.user_id
                    WHERE u.email = %s AND u.is_active = TRUE
                """, (email,))
                return await cursor.fetchone()
    
    async def update_last_login(self, user_id: str):
        """
        마지막 로그인 시간 업데이트
        
        Args:
            user_id (str): 사용자 ID
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE users SET last_login = NOW() WHERE user_id = %s",
                    (user_id,)
                )
    
    async def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 프로필 업데이트
        
        Args:
            user_id (str): 사용자 ID
            profile_data (Dict[str, Any]): 업데이트할 프로필 정보 딕셔너리
        
        Returns:
            Dict[str, Any]: 업데이트된 사용자 정보
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # 사용자 정보 업데이트
                    if any(key in profile_data for key in ['full_name', 'email']):
                        user_updates = []
                        user_values = []
                        
                        if 'full_name' in profile_data:
                            user_updates.append("full_name = %s")
                            user_values.append(profile_data['full_name'])
                        if 'email' in profile_data:
                            user_updates.append("email = %s")
                            user_values.append(profile_data['email'])
                        
                        user_values.append(user_id)
                        
                        await cursor.execute(f"""
                            UPDATE users SET {', '.join(user_updates)}, updated_at = NOW()
                            WHERE user_id = %s
                        """, user_values)
                    
                    # 프로필 정보 업데이트
                    profile_updates = []
                    profile_values = []
                    
                    for key in ['phone', 'birth_date', 'gender', 'profile_image_url', 'bio']:
                        if key in profile_data:
                            profile_updates.append(f"{key} = %s")
                            profile_values.append(profile_data[key])
                    
                    if profile_updates:
                        profile_values.append(user_id)
                        await cursor.execute(f"""
                            UPDATE user_profiles SET {', '.join(profile_updates)}, updated_at = NOW()
                            WHERE user_id = %s
                        """, profile_values)
                    
                    # 업데이트된 사용자 정보 반환
                    return await self.get_user_by_user_id(user_id)
                    
                except Exception as e:
                    await connection.rollback()
                    raise e
    
    async def save_refresh_token(self, user_id: str, token_hash: str, expires_at: datetime):
        """
        리프레시 토큰 저장
        
        Args:
            user_id (str): 사용자 ID
            token_hash (str): 해시화된 리프레시 토큰
            expires_at (datetime): 토큰 만료 시간
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                """, (user_id, token_hash, expires_at))
    
    async def verify_refresh_token(self, token_hash: str) -> Optional[str]:
        """
        리프레시 토큰 검증
        
        Args:
            token_hash (str): 해시화된 리프레시 토큰
        
        Returns:
            Optional[str]: 사용자 ID, 토큰이 유효하지 않으면 None
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT user_id FROM refresh_tokens
                    WHERE token_hash = %s AND expires_at > NOW() AND is_revoked = FALSE
                """, (token_hash,))
                result = await cursor.fetchone()
                return result['user_id'] if result else None
    
    async def revoke_refresh_token(self, token_hash: str):
        """
        리프레시 토큰 무효화
        
        Args:
            token_hash (str): 해시화된 리프레시 토큰
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE refresh_tokens SET is_revoked = TRUE WHERE token_hash = %s",
                    (token_hash,)
                )
    
    async def revoke_all_user_tokens(self, user_id: str):
        """
        사용자의 모든 리프레시 토큰 무효화
        
        Args:
            user_id (str): 사용자 ID
        """
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = %s",
                    (user_id,)
                )