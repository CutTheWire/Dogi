import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import NoReturn, List, Optional, Dict, Any
from databases import Database
from sqlalchemy import text

class MySQLDBHandler:
    def __init__(self) -> NoReturn:
        """
        MySQL 데이터베이스 초기 설정 및 연결 URL 구성
        """
        # .env 파일 로드
        env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
        load_dotenv(env_file_path)
        self.database_name = os.getenv('MYSQL_DATABASE')

        self.database = Database(
            f"mysql://{os.getenv('MYSQL_ROOT_USER')}:" \
            f"{os.getenv('MYSQL_ROOT_PASSWORD')}@" \
            f"{os.getenv('MYSQL_ROOT_HOST')}:" \
            f"{os.getenv('MYSQL_ROOT_PORT')}/" \
            f"{os.getenv('MYSQL_DATABASE')}"
        )
            
    async def connect(self):
        '''
        데이터베이스 연결
        '''
        await self.database.connect()

    async def disconnect(self):
        '''
        데이터베이스 연결 해제
        '''
        await self.database.disconnect()

    async def test_connection(self):
        """
        MySQL 연결 테스트
        """
        try:
            result = await self.database.fetch_one("SELECT 1 as test")
            print(f"MySQL 연결 테스트 성공: {result}")
        except Exception as e:
            print(f"MySQL 연결 테스트 실패: {e}")
            raise e

    async def fetch_all(self, query: str, params: dict = None) -> List[dict]:
        """
        SELECT 쿼리 실행 후 결과 리스트 반환
        """
        try:
            return await self.database.fetch_all(query=query, values=params)
        except Exception as e:
            print(f"Query fetch_all 실패: {e}")
            raise e

    async def fetch_one(self, query: str, params: dict = None) -> Optional[dict]:
        """
        SELECT 쿼리 실행 후 단일 결과 반환
        """
        try:
            result = await self.database.fetch_one(query=query, values=params)
            return dict(result) if result else None
        except Exception as e:
            print(f"Query fetch_one 실패: {e}")
            raise e

    async def execute(self, query: str, params: dict = None):
        """
        INSERT, UPDATE, DELETE 쿼리 실행
        """
        try:
            return await self.database.execute(query=query, values=params)
        except Exception as e:
            print(f"Query execute 실패: {e}")
            raise e

    async def get_tables(self) -> List[str]:
        """
        데이터베이스 내 모든 테이블 이름 반환
        """
        try:
            query = "SHOW TABLES"
            tables = await self.fetch_all(query)
            return [table[f'Tables_in_{self.database_name}'] for table in tables]
        except Exception as e:
            print(f"테이블 목록 조회 실패: {e}")
            return []

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        새로운 사용자 생성
        
        Args:
            user_data: 사용자 데이터
            
        Returns:
            Dict: 생성된 사용자 정보
        """
        try:
            # 사용자 ID 및 이메일 중복 체크
            check_query = """
                SELECT user_id, email FROM users 
                WHERE user_id = :user_id OR email = :email
            """
            existing_user = await self.fetch_one(check_query, {
                'user_id': user_data["user_id"],
                'email': user_data["email"]
            })
            
            if existing_user:
                if existing_user["user_id"] == user_data["user_id"]:
                    raise ValueError("이미 사용 중인 사용자 ID입니다.")
                if existing_user["email"] == user_data["email"]:
                    raise ValueError("이미 사용 중인 이메일 주소입니다.")
            
            # 사용자 생성
            insert_user_query = """
                INSERT INTO users (user_id, email, password_hash, full_name, is_active, is_verified)
                VALUES (:user_id, :email, :password_hash, :full_name, :is_active, :is_verified)
            """
            await self.execute(insert_user_query, {
                'user_id': user_data["user_id"],
                'email': user_data["email"],
                'password_hash': user_data["password_hash"],
                'full_name': user_data["full_name"],
                'is_active': user_data.get("is_active", True),
                'is_verified': user_data.get("is_verified", False)
            })
            
            # 프로필 생성 (phone, birth_date, gender가 있는 경우)
            if any(key in user_data for key in ["phone", "birth_date", "gender"]):
                insert_profile_query = """
                    INSERT INTO user_profiles (user_id, phone, birth_date, gender)
                    VALUES (:user_id, :phone, :birth_date, :gender)
                """
                await self.execute(insert_profile_query, {
                    'user_id': user_data["user_id"],
                    'phone': user_data.get("phone"),
                    'birth_date': user_data.get("birth_date"),
                    'gender': user_data.get("gender")
                })
            
            # 생성된 사용자 정보 조회
            user = await self.get_user_by_user_id(user_data["user_id"])
            return user
            
        except ValueError:
            raise
        except Exception as e:
            print(f"사용자 생성 실패: {e}")
            raise e

    async def get_user_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 사용자 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            Optional[Dict]: 사용자 정보
        """
        try:
            query = """
                SELECT u.*, up.phone, up.birth_date, up.gender, up.profile_image_url, up.bio
                FROM users u
                LEFT JOIN user_profiles up ON u.user_id = up.user_id
                WHERE u.user_id = :user_id
            """
            return await self.fetch_one(query, {'user_id': user_id})
        except Exception as e:
            print(f"사용자 조회 실패: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        이메일로 사용자 조회
        
        Args:
            email: 이메일 주소
            
        Returns:
            Optional[Dict]: 사용자 정보
        """
        try:
            query = """
                SELECT u.*, up.phone, up.birth_date, up.gender, up.profile_image_url, up.bio
                FROM users u
                LEFT JOIN user_profiles up ON u.user_id = up.user_id
                WHERE u.email = :email
            """
            return await self.fetch_one(query, {'email': email})
        except Exception as e:
            print(f"사용자 조회 실패: {e}")
            return None

    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        전화번호로 사용자 조회
        
        Args:
            phone: 전화번호
            
        Returns:
            Optional[Dict]: 사용자 정보
        """
        try:
            query = """
                SELECT u.*, up.phone, up.birth_date, up.gender, up.profile_image_url, up.bio
                FROM users u
                LEFT JOIN user_profiles up ON u.user_id = up.user_id
                WHERE up.phone = :phone
            """
            return await self.fetch_one(query, {'phone': phone})
        except Exception as e:
            print(f"전화번호로 사용자 조회 실패: {e}")
            return None

    async def update_last_login(self, user_id: str):
        """
        마지막 로그인 시간 업데이트
        
        Args:
            user_id: 사용자 ID
        """
        try:
            query = """
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE user_id = :user_id
            """
            await self.execute(query, {'user_id': user_id})
        except Exception as e:
            print(f"로그인 시간 업데이트 실패: {e}")

    async def save_refresh_token(self, user_id: str, token_hash: str, expires_at: datetime):
        """
        리프레시 토큰 저장
        
        Args:
            user_id: 사용자 ID
            token_hash: 토큰 해시
            expires_at: 만료 시간
        """
        try:
            query = """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, :expires_at)
            """
            await self.execute(query, {
                'user_id': user_id,
                'token_hash': token_hash,
                'expires_at': expires_at
            })
        except Exception as e:
            print(f"리프레시 토큰 저장 실패: {e}")
            raise e

    async def verify_refresh_token(self, token_hash: str) -> Optional[str]:
        """
        리프레시 토큰 검증
        
        Args:
            token_hash: 토큰 해시
            
        Returns:
            Optional[str]: 사용자 ID (유효한 경우)
        """
        try:
            query = """
                SELECT user_id FROM refresh_tokens 
                WHERE token_hash = :token_hash 
                AND expires_at > CURRENT_TIMESTAMP 
                AND is_revoked = FALSE
            """
            result = await self.fetch_one(query, {'token_hash': token_hash})
            return result["user_id"] if result else None
        except Exception as e:
            print(f"리프레시 토큰 검증 실패: {e}")
            return None

    async def revoke_refresh_token(self, token_hash: str):
        """
        리프레시 토큰 무효화
        
        Args:
            token_hash: 토큰 해시
        """
        try:
            query = """
                UPDATE refresh_tokens 
                SET is_revoked = TRUE 
                WHERE token_hash = :token_hash
            """
            await self.execute(query, {'token_hash': token_hash})
        except Exception as e:
            print(f"리프레시 토큰 무효화 실패: {e}")

    async def update_user_profile(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 프로필 업데이트
        
        Args:
            user_id: 사용자 ID
            update_data: 업데이트할 데이터
            
        Returns:
            Dict: 업데이트된 사용자 정보
        """
        try:
            # users 테이블 업데이트 (email, full_name)
            user_fields = []
            user_params = {'user_id': user_id}
            
            if "email" in update_data:
                user_fields.append("email = :email")
                user_params['email'] = update_data["email"]
            if "full_name" in update_data:
                user_fields.append("full_name = :full_name")
                user_params['full_name'] = update_data["full_name"]
            
            if user_fields:
                user_query = f"""
                    UPDATE users 
                    SET {', '.join(user_fields)}, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = :user_id
                """
                await self.execute(user_query, user_params)
            
            # user_profiles 테이블 업데이트
            profile_fields = []
            profile_params = {'user_id': user_id}
            
            for field in ["phone", "birth_date", "gender", "bio"]:
                if field in update_data:
                    profile_fields.append(f"{field} = :{field}")
                    profile_params[field] = update_data[field]
            
            if profile_fields:
                # UPSERT 구문 사용
                upsert_query = f"""
                    INSERT INTO user_profiles (user_id, {', '.join(profile_params.keys() - {'user_id'})})
                    VALUES (:user_id, {', '.join([f':{k}' for k in profile_params.keys() - {'user_id'}])})
                    ON DUPLICATE KEY UPDATE 
                    {', '.join(profile_fields)}, updated_at = CURRENT_TIMESTAMP
                """
                await self.execute(upsert_query, profile_params)
            
            # 업데이트된 사용자 정보 조회
            user = await self.get_user_by_user_id(user_id)
            return user
            
        except Exception as e:
            print(f"사용자 프로필 업데이트 실패: {e}")
            raise e

    async def create_verification_code(self, code: str, userid: str):
        """
        인증 코드 생성 또는 갱신 (만료 시간: 15분)
        """
        try:
            check_query = """
                SELECT id FROM email_verification
                WHERE userid = :userid
            """
            result = await self.fetch_one(check_query, {'userid': userid})
            
            expiration_time = datetime.now() + timedelta(minutes=15)
            
            if result is None:
                insert_query = """
                    INSERT INTO email_verification (userid, verification_code, expiry_time)
                    VALUES (:userid, :code, :expiration_time)
                """
                await self.execute(insert_query, {
                    'userid': userid,
                    'code': code,
                    'expiration_time': expiration_time
                })
            else:
                update_query = """
                    UPDATE email_verification
                    SET verification_code = :code, expiry_time = :expiration_time
                    WHERE userid = :userid
                """
                await self.execute(update_query, {
                    'userid': userid,
                    'code': code,
                    'expiration_time': expiration_time
                })
        except Exception as e:
            print(f"인증 코드 생성 실패: {e}")
            raise e

    async def code_verification(self, code: str, userid: str, email: str) -> str:
        """
        인증 코드 검증 및 만료 여부 확인
        """
        try:
            check_query = """
                SELECT verification_code, expiry_time
                FROM email_verification
                WHERE userid = :userid
            """
            result = await self.fetch_one(check_query, {'userid': userid})
            
            if result is None:
                return "code not found"
            
            verification_code, expiry_time = result["verification_code"], result["expiry_time"]
            
            if expiry_time < datetime.now():
                delete_query = """
                    DELETE FROM email_verification
                    WHERE userid = :userid
                """
                await self.execute(delete_query, {'userid': userid})
                return "code is expired"
            
            if verification_code == code:
                delete_query = """
                    DELETE FROM email_verification
                    WHERE userid = :userid
                """
                await self.execute(delete_query, {'userid': userid})
                
                update_membership_query = """
                    UPDATE users
                    SET is_verified = TRUE,
                        email = :email
                    WHERE user_id = :userid
                """
                await self.execute(update_membership_query, {
                    'userid': userid, 
                    'email': email
                })
                
                return "success"
            else:
                return "code is different"
                
        except Exception as e:
            print(f"인증 코드 검증 실패: {e}")
            raise e