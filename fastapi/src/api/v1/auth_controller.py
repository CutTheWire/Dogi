from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional

from core import dependencies
from domain import Schema, ErrorTools
from service import (
    MySQLClient,
    JWTService
)

auth_router = APIRouter()

@auth_router.post("/register", summary="회원가입", status_code=201)
async def register(
    request: Schema.UserRegisterRequest,
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client),
    jwt_service: JWTService.JWTHandler = Depends(dependencies.get_jwt_service)
):
    """
    새로운 사용자를 등록합니다.
    
    Args:
        request: 회원가입 요청 데이터
        mysql_handler: MySQL 핸들러
        jwt_service: JWT 서비스
    
    Returns:
        JSONResponse: 등록된 사용자 정보와 토큰
    """
    try:
        # 비밀번호 해시화
        password_hash = jwt_service.hash_password(request.password)
        
        # 사용자 데이터 준비
        user_data = {
            "user_id": request.user_id,
            "email": request.email,
            "password_hash": password_hash,
            "full_name": request.full_name,
            "phone": request.phone,
            "birth_date": request.birth_date,
            "gender": request.gender.value if request.gender else None,
            "is_active": True,
            "is_verified": False
        }
        
        # 사용자 생성
        user = await mysql_handler.create_user(user_data)
        
        # 토큰 생성
        access_token = jwt_service.create_access_token({"sub": user["user_id"]})
        refresh_token, refresh_token_hash, expires_at = jwt_service.create_refresh_token(user["user_id"])
        
        # 리프레시 토큰 저장
        await mysql_handler.save_refresh_token(user["user_id"], refresh_token_hash, expires_at)
        
        # 사용자 정보 응답 (비밀번호 제외)
        user_response = Schema.UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            phone=user.get("phone"),
            birth_date=user.get("birth_date"),
            gender=user.get("gender"),
            profile_image_url=user.get("profile_image_url"),
            bio=user.get("bio"),
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user.get("last_login")
        )
        
        return JSONResponse(
            content={
                "message": "회원가입이 완료되었습니다.",
                "user": user_response.model_dump(),
                "tokens": Schema.TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=jwt_service.access_token_expire_minutes * 60
                ).model_dump()
            },
            status_code=201
        )
        
    except ValueError as e:
        raise ErrorTools.ValueErrorException(detail=str(e))
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"회원가입 중 오류: {str(e)}")

@auth_router.post("/login", summary="로그인")
async def login(
    request: Schema.UserLoginRequest,
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client),
    jwt_service: JWTService.JWTHandler = Depends(dependencies.get_jwt_service)
):
    """
    사용자 로그인을 처리합니다.
    
    Args:
        request: 로그인 요청 데이터
        mysql_handler: MySQL 핸들러
        jwt_service: JWT 서비스
    
    Returns:
        JSONResponse: 로그인 토큰과 사용자 정보
    """
    try:
        # 사용자 조회 (user_id 또는 email로)
        user = None
        if "@" in request.user_id:
            user = await mysql_handler.get_user_by_email(request.user_id)
        else:
            user = await mysql_handler.get_user_by_user_id(request.user_id)
        
        if not user:
            raise ErrorTools.UnauthorizedException(detail="잘못된 사용자 ID 또는 비밀번호입니다.")
        
        # 비밀번호 검증
        if not jwt_service.verify_password(request.password, user["password_hash"]):
            raise ErrorTools.UnauthorizedException(detail="잘못된 사용자 ID 또는 비밀번호입니다.")
        
        # 마지막 로그인 시간 업데이트
        await mysql_handler.update_last_login(user["user_id"])
        
        # 토큰 생성
        access_token = jwt_service.create_access_token({"sub": user["user_id"]})
        refresh_token, refresh_token_hash, expires_at = jwt_service.create_refresh_token(user["user_id"])
        
        # 리프레시 토큰 저장
        await mysql_handler.save_refresh_token(user["user_id"], refresh_token_hash, expires_at)
        
        # 사용자 정보 응답
        user_response = Schema.UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            phone=user.get("phone"),
            birth_date=user.get("birth_date"),
            gender=user.get("gender"),
            profile_image_url=user.get("profile_image_url"),
            bio=user.get("bio"),
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user.get("last_login")
        )
        
        return {
            "message": "로그인이 완료되었습니다.",
            "user": user_response.model_dump(),
            "tokens": Schema.TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=jwt_service.access_token_expire_minutes * 60
            ).model_dump()
        }
        
    except ErrorTools.UnauthorizedException:
        raise
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"로그인 중 오류: {str(e)}")

@auth_router.post("/refresh", summary="토큰 갱신")
async def refresh_token(
    request: Schema.RefreshTokenRequest,
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client),
    jwt_service: JWTService.JWTHandler = Depends(dependencies.get_jwt_service)
):
    """
    리프레시 토큰으로 새로운 액세스 토큰을 발급합니다.
    
    Args:
        request: 토큰 갱신 요청
        mysql_handler: MySQL 핸들러
        jwt_service: JWT 서비스
    
    Returns:
        JSONResponse: 새로운 액세스 토큰
    """
    try:
        # 리프레시 토큰 해시화
        token_hash = jwt_service.hash_refresh_token(request.refresh_token)
        
        # 토큰 검증
        user_id = await mysql_handler.verify_refresh_token(token_hash)
        if not user_id:
            raise ErrorTools.UnauthorizedException(detail="유효하지 않은 리프레시 토큰입니다.")
        
        # 기존 토큰 무효화
        await mysql_handler.revoke_refresh_token(token_hash)
        
        # 새로운 토큰 생성
        access_token = jwt_service.create_access_token({"sub": user_id})
        new_refresh_token, new_refresh_token_hash, expires_at = jwt_service.create_refresh_token(user_id)
        
        # 새로운 리프레시 토큰 저장
        await mysql_handler.save_refresh_token(user_id, new_refresh_token_hash, expires_at)
        
        return Schema.TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=jwt_service.access_token_expire_minutes * 60
        ).model_dump()
        
    except ErrorTools.UnauthorizedException:
        raise
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"토큰 갱신 중 오류: {str(e)}")

@auth_router.post("/logout", summary="로그아웃")
async def logout(
    request: Schema.RefreshTokenRequest,
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client),
    jwt_service: JWTService.JWTHandler = Depends(dependencies.get_jwt_service)
):
    """
    사용자 로그아웃을 처리합니다.
    
    Args:
        request: 로그아웃 요청 (리프레시 토큰)
        mysql_handler: MySQL 핸들러
        jwt_service: JWT 서비스
    
    Returns:
        JSONResponse: 로그아웃 완료 메시지
    """
    try:
        # 리프레시 토큰 해시화
        token_hash = jwt_service.hash_refresh_token(request.refresh_token)
        
        # 토큰 무효화
        await mysql_handler.revoke_refresh_token(token_hash)
        
        return {"message": "로그아웃이 완료되었습니다."}
        
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"로그아웃 중 오류: {str(e)}")

@auth_router.get("/profile", summary="프로필 조회")
async def get_profile(
    user_id: str = Depends(dependencies.get_current_user_id),
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client)
):
    """
    현재 사용자의 프로필을 조회합니다.
    
    Args:
        user_id: 현재 사용자 ID
        mysql_handler: MySQL 핸들러
    
    Returns:
        JSONResponse: 사용자 프로필 정보
    """
    try:
        user = await mysql_handler.get_user_by_user_id(user_id)
        if not user:
            raise ErrorTools.NotFoundException(detail="사용자를 찾을 수 없습니다.")
        
        user_response = Schema.UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            phone=user.get("phone"),
            birth_date=user.get("birth_date"),
            gender=user.get("gender"),
            profile_image_url=user.get("profile_image_url"),
            bio=user.get("bio"),
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user.get("last_login")
        )
        
        return user_response.model_dump()
        
    except ErrorTools.NotFoundException:
        raise
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"프로필 조회 중 오류: {str(e)}")

@auth_router.patch("/profile", summary="프로필 수정")
async def update_profile(
    request: Schema.UserProfileUpdateRequest,
    user_id: str = Depends(dependencies.get_current_user_id),
    mysql_handler: MySQLClient.MongoDBHandler = Depends(dependencies.get_mysql_client)
):
    """
    현재 사용자의 프로필을 수정합니다.
    
    Args:
        request: 프로필 수정 요청
        user_id: 현재 사용자 ID
        mysql_handler: MySQL 핸들러
    
    Returns:
        JSONResponse: 수정된 사용자 프로필
    """
    try:
        # 수정할 데이터 준비
        update_data = {}
        if request.full_name is not None:
            update_data["full_name"] = request.full_name
        if request.email is not None:
            update_data["email"] = request.email
        if request.phone is not None:
            update_data["phone"] = request.phone
        if request.birth_date is not None:
            update_data["birth_date"] = request.birth_date
        if request.gender is not None:
            update_data["gender"] = request.gender.value
        if request.bio is not None:
            update_data["bio"] = request.bio
        
        # 프로필 업데이트
        user = await mysql_handler.update_user_profile(user_id, update_data)
        
        user_response = Schema.UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            phone=user.get("phone"),
            birth_date=user.get("birth_date"),
            gender=user.get("gender"),
            profile_image_url=user.get("profile_image_url"),
            bio=user.get("bio"),
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user.get("last_login")
        )
        
        return {
            "message": "프로필이 성공적으로 수정되었습니다.",
            "user": user_response.model_dump()
        }
        
    except Exception as e:
        raise ErrorTools.InternalServerErrorException(detail=f"프로필 수정 중 오류: {str(e)}")
