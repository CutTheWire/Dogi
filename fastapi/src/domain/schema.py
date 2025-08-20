from pydantic import BaseModel, EmailStr, Field, field_validator, conint
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

class GenderEnum(str, Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"

class CommonFields:
    # 기존 LLM 관련 필드들
    content_set: str = Field(
        example="우리 강아지가 갑자기 토하고 설사를 해요.",
        title="사용자 메시지 내용",
        description="사용자가 입력한 메시지 내용",
    )
    
    model_id_set: str = Field(
        example="llama3",
        title="모델 ID",
        description="사용할 AI 모델의 ID",
    )
    
    message_idx_set: int = Field(
        example=1,
        title="세션 메시지 인덱스",
        description="세션 내 메시지의 인덱스",
    )

    # 사용자 인증 관련 필드들
    user_id_set: str = Field(
        example="john_doe",
        title="사용자 ID",
        description="사용자 고유 ID (영문, 숫자만 가능)",
        min_length=3,
        max_length=50
    )
    
    email_set: EmailStr = Field(
        example="john.doe@example.com",
        title="이메일 주소",
        description="사용자 이메일 주소"
    )
    
    password_set: str = Field(
        example="SecurePassword123!",
        title="비밀번호",
        description="사용자 비밀번호 (최소 8자)",
        min_length=8,
        max_length=128
    )
    
    full_name_set: str = Field(
        example="홍길동",
        title="전체 이름",
        description="사용자의 전체 이름",
        min_length=1,
        max_length=100
    )
    
    phone_set: Optional[str] = Field(
        None,
        example="010-1234-5678",
        title="전화번호",
        description="사용자 전화번호",
        max_length=20
    )
    
    birth_date_set: Optional[date] = Field(
        None,
        example="1990-01-01",
        title="생년월일",
        description="사용자 생년월일"
    )
    
    gender_set: Optional[GenderEnum] = Field(
        None,
        example="M",
        title="성별",
        description="사용자 성별 (M: 남성, F: 여성, O: 기타)"
    )
    
    bio_set: Optional[str] = Field(
        None,
        example="안녕하세요! 반려동물을 사랑하는 사용자입니다.",
        title="자기소개",
        description="사용자 자기소개",
        max_length=500
    )
    
    access_token_set: str = Field(
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        title="액세스 토큰",
        description="JWT 액세스 토큰"
    )
    
    refresh_token_set: str = Field(
        example="abc123def456ghi789...",
        title="리프레시 토큰",
        description="JWT 리프레시 토큰"
    )
    
    token_type_set: str = Field(
        default="bearer",
        example="bearer",
        title="토큰 타입",
        description="토큰 타입"
    )
    
    expires_in_set: int = Field(
        example=1800,
        title="토큰 만료 시간",
        description="토큰 만료 시간 (초 단위)"
    )

# 기존 LLM 관련 스키마들
class MessageRequest(BaseModel):
    """
    LLM 세션에 메시지 추가 요청 모델
    """
    content: str = CommonFields.content_set
    model_id: str = CommonFields.model_id_set

class MessageUpdateRequest(BaseModel):
    """
    LLM 세션 마지막 메시지 수정 요청 모델
    """
    content: str = CommonFields.content_set
    model_id: str = CommonFields.model_id_set
    message_idx: int = CommonFields.message_idx_set

class RegenerateRequest(BaseModel):
    """
    LLM 세션 마지막 메시지 재생성 요청 모델
    """
    model_id: str = CommonFields.model_id_set

# 사용자 인증 관련 스키마들
class UserRegisterRequest(BaseModel):
    """
    사용자 회원가입 요청 모델
    """
    user_id: str = CommonFields.user_id_set
    email: EmailStr = CommonFields.email_set
    password: str = CommonFields.password_set
    full_name: str = CommonFields.full_name_set
    phone: Optional[str] = CommonFields.phone_set
    birth_date: Optional[date] = CommonFields.birth_date_set
    gender: Optional[GenderEnum] = CommonFields.gender_set
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        if not v.isalnum():
            raise ValueError('사용자 ID는 영문과 숫자만 사용 가능합니다.')
        return v

class UserLoginRequest(BaseModel):
    """
    사용자 로그인 요청 모델
    """
    user_id: str = Field(
        example="john_doe",
        title="사용자 ID 또는 이메일",
        description="사용자 ID 또는 이메일 주소"
    )
    password: str = CommonFields.password_set

class UserProfileUpdateRequest(BaseModel):
    """
    사용자 프로필 수정 요청 모델
    """
    full_name: Optional[str] = Field(
        None,
        example="홍길동",
        title="전체 이름",
        description="수정할 사용자 전체 이름",
        min_length=1,
        max_length=100
    )
    email: Optional[EmailStr] = Field(
        None,
        example="new.email@example.com",
        title="이메일 주소",
        description="수정할 이메일 주소"
    )
    phone: Optional[str] = CommonFields.phone_set
    birth_date: Optional[date] = CommonFields.birth_date_set
    gender: Optional[GenderEnum] = CommonFields.gender_set
    bio: Optional[str] = CommonFields.bio_set

class TokenResponse(BaseModel):
    """
    토큰 응답 모델
    """
    access_token: str = CommonFields.access_token_set
    refresh_token: str = CommonFields.refresh_token_set
    token_type: str = CommonFields.token_type_set
    expires_in: int = CommonFields.expires_in_set

class RefreshTokenRequest(BaseModel):
    """
    토큰 갱신 요청 모델
    """
    refresh_token: str = CommonFields.refresh_token_set

class UserResponse(BaseModel):
    """
    사용자 정보 응답 모델
    """
    user_id: str = Field(
        example="john_doe",
        title="사용자 ID",
        description="사용자 고유 ID"
    )
    email: str = Field(
        example="john.doe@example.com",
        title="이메일 주소",
        description="사용자 이메일 주소"
    )
    full_name: str = Field(
        example="홍길동",
        title="전체 이름",
        description="사용자 전체 이름"
    )
    phone: Optional[str] = Field(
        None,
        example="010-1234-5678",
        title="전화번호",
        description="사용자 전화번호"
    )
    birth_date: Optional[date] = Field(
        None,
        example="1990-01-01",
        title="생년월일",
        description="사용자 생년월일"
    )
    gender: Optional[str] = Field(
        None,
        example="M",
        title="성별",
        description="사용자 성별"
    )
    profile_image_url: Optional[str] = Field(
        None,
        example="https://example.com/profile.jpg",
        title="프로필 이미지 URL",
        description="사용자 프로필 이미지 URL"
    )
    bio: Optional[str] = Field(
        None,
        example="안녕하세요! 반려동물을 사랑하는 사용자입니다.",
        title="자기소개",
        description="사용자 자기소개"
    )
    is_verified: bool = Field(
        example=False,
        title="인증 상태",
        description="사용자 계정 인증 상태"
    )
    created_at: datetime = Field(
        example="2024-01-01T00:00:00",
        title="가입일시",
        description="계정 생성 일시"
    )
    last_login: Optional[datetime] = Field(
        None,
        example="2024-01-01T12:00:00",
        title="마지막 로그인",
        description="마지막 로그인 일시"
    )