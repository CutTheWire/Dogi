# v1 Auth API 구성

## Auth 라우터

|메서드|경로|설명|
|---|---|---|
|POST|/v1/auth/register|회원가입|
|POST|/v1/auth/login|로그인|
|POST|/v1/auth/refresh|토큰 갱신|
|POST|/v1/auth/logout|로그아웃|
|GET|/v1/auth/profile|프로필 조회|
|PATCH|/v1/auth/profile|프로필 수정|

### 회원가입 (POST /v1/auth/register)
- 설명: 새로운 사용자를 등록합니다.

- 요청 본문
```json
{
  "user_id": "john_doe",
  "email": "john@example.com",
  "password": "password123!",
  "full_name": "홍길동",
  "phone": "010-1234-5678",
  "birth_date": "1990-01-01",
  "gender": "male"
}
```

- 201 응답
```json
{
  "message": "회원가입이 완료되었습니다.",
  "user": {
    "user_id": "john_doe",
    "email": "john@example.com",
    "full_name": "홍길동",
    "phone": "010-1234-5678",
    "birth_date": "1990-01-01",
    "gender": "male",
    "profile_image_url": null,
    "bio": null,
    "is_verified": false,
    "created_at": "2024-01-01T12:00:00Z",
    "last_login": null
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "expires_in": 3600
  }
}
```

- 409 에러 (중복)
```json
{
  "detail": "이미 사용중인 사용자 ID입니다."
}
```

### 로그인 (POST /v1/auth/login)
- 설명: 사용자 로그인을 처리합니다. (user_id 또는 email로 로그인 가능)

- 요청 본문
```json
{
  "user_id": "john_doe",
  "password": "password123!"
}
```

또는 이메일로 로그인:
```json
{
  "user_id": "john@example.com",
  "password": "password123!"
}
```

- 200 응답
```json
{
  "message": "로그인이 완료되었습니다.",
  "user": {
    "user_id": "john_doe",
    "email": "john@example.com",
    "full_name": "홍길동",
    "phone": "010-1234-5678",
    "birth_date": "1990-01-01",
    "gender": "male",
    "profile_image_url": null,
    "bio": null,
    "is_verified": false,
    "created_at": "2024-01-01T12:00:00Z",
    "last_login": "2024-01-01T12:30:00Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "expires_in": 3600
  }
}
```

- 401 에러 (인증 실패)
```json
{
  "detail": "잘못된 사용자 ID 또는 비밀번호입니다."
}
```

### 토큰 갱신 (POST /v1/auth/refresh)
- 설명: 리프레시 토큰으로 새로운 액세스 토큰을 발급합니다.

- 요청 본문
```json
{
  "refresh_token": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

- 200 응답
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a6e9c9b3e91b22a8d6c88ed3b9c2d1a5f2b8e7c4d6a9f1b2c3d4e5f6a7b8c9d0",
  "expires_in": 3600
}
```

- 401 에러 (토큰 무효)
```json
{
  "detail": "유효하지 않은 리프레시 토큰입니다."
}
```

### 로그아웃 (POST /v1/auth/logout)
- 설명: 사용자 로그아웃을 처리합니다. (리프레시 토큰 무효화)

- 요청 본문
```json
{
  "refresh_token": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

- 200 응답
```json
{
  "message": "로그아웃이 완료되었습니다."
}
```

### 프로필 조회 (GET /v1/auth/profile)
- 설명: 현재 사용자의 프로필을 조회합니다.
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 200 응답
```json
{
  "user_id": "john_doe",
  "email": "john@example.com",
  "full_name": "홍길동",
  "phone": "010-1234-5678",
  "birth_date": "1990-01-01",
  "gender": "male",
  "profile_image_url": "https://example.com/profile.jpg",
  "bio": "안녕하세요! 반려동물을 사랑하는 홍길동입니다.",
  "is_verified": true,
  "created_at": "2024-01-01T12:00:00Z",
  "last_login": "2024-01-01T12:30:00Z"
}
```

- 401 에러 (인증 실패)
```json
{
  "detail": "Token validation failed: 토큰이 만료되었습니다."
}
```

- 404 에러 (사용자 없음)
```json
{
  "detail": "사용자를 찾을 수 없습니다."
}
```

### 프로필 수정 (PATCH /v1/auth/profile)
- 설명: 현재 사용자의 프로필을 수정합니다.
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 요청 본문 (모든 필드 선택사항)
```json
{
  "full_name": "김철수",
  "email": "kim@example.com",
  "phone": "010-9876-5432",
  "birth_date": "1985-05-15",
  "gender": "male",
  "bio": "반려동물과 함께하는 행복한 일상을 공유합니다."
}
```

- 200 응답
```json
{
  "message": "프로필이 성공적으로 수정되었습니다.",
  "user": {
    "user_id": "john_doe",
    "email": "kim@example.com",
    "full_name": "김철수",
    "phone": "010-9876-5432",
    "birth_date": "1985-05-15",
    "gender": "male",
    "profile_image_url": "https://example.com/profile.jpg",
    "bio": "반려동물과 함께하는 행복한 일상을 공유합니다.",
    "is_verified": true,
    "created_at": "2024-01-01T12:00:00Z",
    "last_login": "2024-01-01T12:30:00Z"
  }
}
```

- 409 에러 (중복)
```json
{
  "detail": "이미 사용중인 이메일입니다."
}
```

## 데이터 모델

### UserRegisterRequest
```json
{
  "user_id": "string (required)",
  "email": "string (required)",
  "password": "string (required)",
  "full_name": "string (required)",
  "phone": "string (optional)",
  "birth_date": "date (optional)",
  "gender": "male|female|other (optional)"
}
```

### UserLoginRequest
```json
{
  "user_id": "string (required) - user_id 또는 email",
  "password": "string (required)"
}
```

### RefreshTokenRequest
```json
{
  "refresh_token": "string (required)"
}
```

### UserProfileUpdateRequest
```json
{
  "full_name": "string (optional)",
  "email": "string (optional)",
  "phone": "string (optional)",
  "birth_date": "date (optional)",
  "gender": "male|female|other (optional)",
  "bio": "string (optional)"
}
```

### UserResponse
```json
{
  "user_id": "string",
  "email": "string",
  "full_name": "string",
  "phone": "string|null",
  "birth_date": "date|null",
  "gender": "string|null",
  "profile_image_url": "string|null",
  "bio": "string|null",
  "is_verified": "boolean",
  "created_at": "datetime",
  "last_login": "datetime|null"
}
```

### TokenResponse
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "expires_in": "integer (seconds)"
}
```

## 인증 및 보안

### JWT 토큰
- **Access Token**: API 요청 시 Authorization 헤더에 Bearer 토큰으로 전송
- **Refresh Token**: 만료된 Access Token 갱신 시 사용
- **토큰 만료**: Access Token은 설정된 시간(기본 1시간) 후 만료

### 비밀번호 보안
- 비밀번호는 해시화되어 저장
- 로그인 시 해시 검증을 통한 인증

### 에러 처리
- **401 Unauthorized**: 인증 실패, 토큰 무효
- **404 Not Found**: 리소스 없음
- **409 Conflict**: 데이터 중복 (ID, 이메일, 전화번호)
- **422 Unprocessable Entity**: 유효성 검사 실패
- **500 Internal Server Error**: 서버 오류

## 사용 예시

### 회원가입부터 API 사용까지의 플로우
```javascript
// 1. 회원가입
const registerResponse = await fetch('/v1/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'john_doe',
    email: 'john@example.com',
    password: 'password123!',
    full_name: '홍길동'
  })
});

const { tokens } = await registerResponse.json();

// 2. 인증이 필요한 API 호출
const profileResponse = await fetch('/v1/auth/profile', {
  headers: {
    'Authorization': `Bearer ${tokens.access_token}`
  }
});

// 3. 토큰 만료 시 갱신
const refreshResponse = await fetch('/v1/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    refresh_token: tokens.refresh_token
  })
});
```