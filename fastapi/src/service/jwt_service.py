import os
import jwt
import hashlib
import secrets
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext

class JWTHandler:
    """
    JWT 토큰 관리 서비스
    """
    
    def __init__(self):
        env_file_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(env_file_path)
        
        self.secret_key = os.getenv('JWT_SECRET_KEY')
        self.algorithm = os.getenv('JWT_ALGORITHM')
        self.access_token_expire_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
        self.refresh_token_expire_days = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS'))
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        """
        비밀번호 해시화
        
        Args:
            password (str): 평문 비밀번호
        
        Returns:
            str: 해시화된 비밀번호
        """
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        비밀번호 검증
        
        Args:
            plain_password (str): 평문 비밀번호
            hashed_password (str): 해시화된 비밀번호
        
        Returns:
            bool: 비밀번호가 일치하는지 여부
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """
        액세스 토큰 생성
        
        Args:
            data (Dict[str, Any]): 토큰에 포함할 데이터
        
        Returns:
            str: 생성된 JWT 액세스 토큰
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str) -> tuple[str, str, datetime]:
        """
        리프레시 토큰 생성
        
        Args:
            user_id (str): 사용자 ID
        
        Returns:
            tuple[str, str, datetime]: 생성된 리프레시 토큰, 해시화된 토큰, 만료 시간
        """
        # 랜덤 토큰 생성
        token = secrets.token_urlsafe(32)
        # 토큰 해시화 (DB 저장용)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # 만료 시간
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        return token, token_hash, expires_at
    
    def hash_refresh_token(self, token: str) -> str:
        """
        리프레시 토큰 해시화
        
        Args:
            token (str): 리프레시 토큰
        
        Returns:
            str: 해시화된 리프레시 토큰
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        토큰 검증
        
        Args:
            token (str): JWT 토큰
        
        Returns:
            Optional[Dict[str, Any]]: 검증된 토큰의 페이로드, None if 검증 실패
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    def extract_user_id(self, token: str) -> Optional[str]:
        """
        토큰에서 사용자 ID 추출
        
        Args:
            token (str): JWT 토큰
        
        Returns:
            Optional[str]: 사용자 ID, 토큰이 유효하지 않으면 None
        """
        payload = self.verify_token(token)
        if payload and payload.get("type") == "access":
            return payload.get("sub")
        return None