# Docker 컨테이너 구성

## 컨테이너 상세 구성

### 1. python-libs-init-dogi
**목적**: Python 라이브러리 사전 설치 및 초기화

```yaml
python-libs-init-dogi:
  build:
    context: ./fastapi
    dockerfile: src/Dockerfile.libs
  container_name: python-libs-init-dogi
  volumes:
    - python-libs:/opt/python-libs
  command: >
    sh -c "
    if [ ! -f /opt/python-libs/.initialized ]; then
      echo 'Installing Python libraries...'
      pip install --target=/opt/python-libs/lib/python3.11/site-packages 'numpy>=1.22.4,<2.0.0'
      pip install --target=/opt/python-libs/lib/python3.11/site-packages torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 -f https://download.pytorch.org/whl/torch_stable.html
      pip install --target=/opt/python-libs/lib/python3.11/site-packages -r requirements.txt
      CMAKE_ARGS='-DGGML_CUDA=ON' pip install --target=/opt/python-libs/lib/python3.11/site-packages llama-cpp-python --no-cache-dir --force-reinstall
      pip install --target=/opt/python-libs/lib/python3.11/site-packages https://github.com/oobabooga/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui/llama_cpp_python_cuda-0.2.62+cu121-cp311-cp311-manylinux_2_31_x86_64.whl
      pip install --target=/opt/python-libs/lib/python3.11/site-packages exllamav2 pynvml uvicorn
      touch /opt/python-libs/.initialized
      echo 'Libraries installation completed!'
    else
      echo 'Libraries already installed, skipping...'
    fi
    "
```

**주요 기능**:
- 일회성 라이브러리 설치 컨테이너
- `.initialized` 파일로 설치 상태 확인
- 설치 완료 시 자동 종료
- 볼륨을 통해 FastAPI 컨테이너와 라이브러리 공유

**설치되는 라이브러리**:
- `numpy>=1.22.4,<2.0.0`
- `torch==2.3.1+cu121`, `torchvision==0.18.1+cu121`, `torchaudio==2.3.1+cu121`
- `llama-cpp-python` (CUDA 지원)
- `exllamav2`, `pynvml`, `uvicorn`
- `requirements.txt`의 모든 의존성

### 2. mysql
**목적**: 사용자 인증 및 프로필 데이터 저장

```yaml
mysql:
  restart: unless-stopped
  build:
    context: ./mysql
  ports:
    - "3306:3306"
  environment:
    MYSQL_DATABASE: ${MYSQL_DATABASE}
    MYSQL_ROOT_HOST: ${MYSQL_ROOT_HOST}
    MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    TZ: Asia/Seoul
  volumes:
    - ./mysql/data:/var/lib/mysql:rw
    - ./mysql/log.cnf:/etc/mysql/conf.d/log.cnf:ro
    - ./mysql/logs:/var/log/mysql:rw
  command: [
    "--character-set-server=utf8mb4", 
    "--collation-server=utf8mb4_unicode_ci",
    "--skip-host-cache",
    "--skip-name-resolve"
    ]
```

**데이터베이스 구조**:
- **users**: 사용자 기본 정보 (user_id, email, password_hash 등)
- **user_profiles**: 사용자 상세 프로필 (full_name, phone, birth_date 등)
- **refresh_tokens**: JWT 리프레시 토큰 관리

**볼륨 마운트**:
- `./mysql/data:/var/lib/mysql` - 데이터 영구 저장 (바인드 마운트)
- `./mysql/log.cnf:/etc/mysql/conf.d/log.cnf` - 로그 설정
- `./mysql/logs:/var/log/mysql` - 로그 파일

**데이터베이스 설정**:
- 문자셋: `utf8mb4`
- 콜레이션: `utf8mb4_unicode_ci`
- 호스트 캐시 비활성화로 성능 최적화
- DNS 역방향 조회 비활성화

### 3. chromadb
**목적**: 벡터 임베딩 저장 및 RAG 시스템 지원

```yaml
chromadb:
  image: chromadb/chroma:latest
  container_name: chromadb
  ports:
    - "7999:7999"
  volumes:
    - chroma-data:/data
  environment:
    - IS_PERSISTENT=TRUE
    - PERSIST_DIRECTORY=/data
    - ANONYMIZED_TELEMETRY=FALSE
  restart: unless-stopped
```

**주요 기능**:
- 의료 문서 벡터 임베딩 저장
- 유사도 검색을 통한 관련 정보 검색
- LangChain VectorRetriever와 연동
- 영구 저장을 통한 데이터 지속성
- 컬렉션: `vet_medical_data`

**설정**:
- 텔레메트리 비활성화
- 영구 저장 활성화
- 자동 재시작 정책

### 4. mongodb
**목적**: LLM 세션 및 대화 기록 저장

```yaml
mongodb:
  restart: unless-stopped
  build:
    context: ./mongo
  ports:
    - "27018:27018"
  environment:
    MONGO_INITDB_ROOT_USERNAME: ${MONGO_ADMIN_USER}
    MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ADMIN_PASSWORD}
    MONGO_DATABASE: ${MONGO_DATABASE}
    TZ: Asia/Seoul
  volumes:
    - ./mongo/data:/data/db:rw
    - ./mongo/logs:/var/logs/mongodb:rw
    - ./.env:/docker-entrypoint-initdb.d/.env:ro
```

**데이터 구조**:
- **llm_sessions**: LLM 대화 세션 정보 (세션 ID, 제목, 생성/수정 날짜)
- **llm_messages**: 세션별 메시지 및 응답 기록 (메시지 인덱스, 질문, 답변)
- 스키마리스 구조로 유연한 데이터 저장

**볼륨 마운트**:
- `./mongo/data:/data/db` - 데이터 영구 저장 (바인드 마운트)
- `./mongo/logs:/var/logs/mongodb` - 로그 파일
- `./.env:/docker-entrypoint-initdb.d/.env` - 초기화 환경변수

**사용자 인증**:
- 관리자 계정으로 초기화
- 환경변수를 통한 인증 정보 주입

### 5. fastapi
**목적**: 메인 API 서버 및 LLM 서빙

```yaml
fastapi:
  restart: always
  build:
    context: ./fastapi
    dockerfile: src/server/Dockerfile
  container_name: fastapi
  ports:
    - "80:80"
  volumes:
    - python-libs:/opt/python-libs:ro
    - ./fastapi/models/:/app/fastapi/models/:rw
    - ./fastapi/logs:/app/logs:rw
    - ./.env:/app/src/.env:ro
  depends_on:
    - python-libs-init-dogi
    - chromadb
    - mongodb
    - mysql
  deploy:
    resources:
      limits:
        memory: 8G
        cpus: '4.0'
      reservations:
        memory: 4G
        devices:
          - driver: nvidia
            capabilities: [gpu]
  environment:
    - TZ=Asia/Seoul
  command: [
    "/usr/local/bin/wait-for-it",
    "mysql:3306", "--",
    "python", "server/server.py"
    ]
```

**리소스 제한**:
- 메모리: 최대 8GB, 예약 4GB
- CPU: 최대 4코어
- GPU: NVIDIA GPU 사용 (CUDA 지원)

**주요 기능**:
- FastAPI 기반 RESTful API 서버
- LLaMA 모델 서빙 (CUDA 가속)
- JWT 기반 인증 시스템 (Auth API)
- 실시간 스트리밍 응답 (LLM API)
- RAG 시스템을 통한 의료 정보 검색

**볼륨 마운트**:
- `python-libs:/opt/python-libs:ro` - 사전 설치된 Python 라이브러리 (읽기 전용)
- `./fastapi/models/:/app/fastapi/models/:rw` - LLaMA 모델 파일
- `./fastapi/logs:/app/logs:rw` - 애플리케이션 로그
- `./.env:/app/src/.env:ro` - 환경변수 파일 (읽기 전용)

**서비스 대기**:
- `wait-for-it` 스크립트로 MySQL 서비스 대기
- 모든 의존성 서비스 준비 후 시작

## 볼륨 구성

```yaml
volumes:
  python-libs:
    driver: local
  chroma-data:
    driver: local
  mysql-data:
    driver: local
```

### python-libs
- **목적**: Python 라이브러리 공유
- **사용**: python-libs-init-dogi ↔ fastapi
- **내용**: AI/ML 라이브러리, CUDA 지원 패키지
- **특징**: 초기화 후 재사용, 빌드 시간 단축

### chroma-data
- **목적**: ChromaDB 데이터 영구 저장
- **내용**: 벡터 임베딩, 인덱스 데이터, 컬렉션 메타데이터
- **특징**: Named volume으로 관리

### mysql-data
- **목적**: MySQL 데이터 영구 저장 (현재 미사용)
- **참고**: 실제로는 바인드 마운트(`./mysql/data`) 사용

## 네트워크 구성

### 포트 매핑
- **80**: FastAPI 서버 (HTTP) - 메인 API 엔드포인트
- **3306**: MySQL 데이터베이스 - 사용자 데이터
- **7999**: ChromaDB API - 벡터 검색
- **27018**: MongoDB - 세션 데이터

### 내부 통신
- 모든 컨테이너는 기본 Docker 네트워크를 통해 통신
- 서비스 이름으로 내부 DNS 해석
- FastAPI에서 `mysql:3306`, `chromadb:7999`, `mongodb:27018`로 접근

### API 엔드포인트
- **Auth API**: `/v1/auth/*` - 사용자 인증 및 프로필 관리
- **LLM API**: `/v1/llm/*` - AI 대화 및 세션 관리
- **Page API**: `/` - 정적 웹페이지 서빙

## 환경 변수

### 공통
- `TZ=Asia/Seoul`: 한국 시간대 설정

### AI/LLM 서비스
- `HUGGING_FACE_TOKEN`: Hugging Face 모델 다운로드 토큰
- `OPENAI_API_KEY`: OpenAI API 키 (백업 모델용)

### JWT 인증
- `JWT_ALGORITHM=HS256`: JWT 알고리즘
- `JWT_SECRET_KEY`: JWT 서명 키
- `ACCESS_TOKEN_EXPIRE_MINUTES=30`: 액세스 토큰 만료 시간
- `REFRESH_TOKEN_EXPIRE_DAYS=7`: 리프레시 토큰 만료 시간

### ChromaDB
- `CHROMA_HOST=chromadb`: ChromaDB 호스트
- `CHROMA_PORT=7999`: ChromaDB 포트
- `CHROMA_COLLECTION_NAME=vet_medical_data`: 컬렉션 이름

### MongoDB
- `MONGO_ADMIN_USER=root`: 관리자 사용자명
- `MONGO_ADMIN_PASSWORD=760329`: 관리자 비밀번호
- `MONGO_DATABASE=dogi`: 사용할 데이터베이스 이름
- `MONGO_HOST=mongodb`: MongoDB 호스트
- `MONGO_PORT=27018`: MongoDB 포트

### MySQL
- `MYSQL_ROOT_USER=root`: 루트 사용자명
- `MYSQL_ROOT_PASSWORD=760329`: 루트 비밀번호
- `MYSQL_DATABASE=dogi`: 데이터베이스 이름
- `MYSQL_ROOT_HOST=mysql`: MySQL 호스트
- `MYSQL_ROOT_PORT=3306`: MySQL 포트

## 빌드 및 실행

### 자동화된 빌드 스크립트
Dogi 프로젝트는 `build_docker.bat` 스크립트를 통해 자동화된 빌드를 제공합니다:

```batch
# 대화형 모드 (기본)
build_docker.bat

# 자동 모드 - 이미지 삭제, 라이브러리 재설치
build_docker.bat -y -y

# 자동 모드 - 이미지 유지, 라이브러리 유지
build_docker.bat -n -n
```

### 빌드 단계별 설명

1. **환경변수 검증**: `.env` 파일 존재 및 필수 변수 확인
2. **Docker 데몬 확인**: Docker Desktop 자동 시작
3. **기존 컨테이너 정리**: `docker-compose down` (볼륨 보존)
4. **선택적 이미지 정리**: 댕글링 이미지 및 빌드 캐시 정리
5. **Python 라이브러리 볼륨 관리**: 재설치 여부 선택
6. **베이스 이미지 빌드**: `dogi-base:latest` 생성
7. **라이브러리 초기화**: `python-libs-init-dogi` 실행 (필요시)
8. **애플리케이션 서비스 빌드**: 병렬 빌드로 성능 최적화
9. **서비스 실행**: 의존성 순서에 따른 시작
10. **상태 확인**: 서비스 정상 동작 확인

### 수동 명령어

```bash
# 전체 스택 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f fastapi

# 개별 서비스 재시작
docker-compose restart fastapi

# Python 라이브러리 재설치
docker-compose up python-libs-init-dogi
```

## 개발 및 운영

### 개발 모드
```bash
# 개발용 빌드 (캐시 없이)
docker-compose build --no-cache

# 특정 서비스만 재빌드
docker-compose build fastapi

# 베이스 이미지 재빌드
docker build -f fastapi/src/Dockerfile.base -t dogi-base:latest .
```

### 모니터링
```bash
# 컨테이너 상태 확인
docker-compose ps

# 리소스 사용량 확인
docker stats

# GPU 사용량 확인 (NVIDIA)
nvidia-smi

# 실시간 로그 모니터링
docker-compose logs -f --tail=100 fastapi
```

### 성능 최적화
- **빌드 캐시 활용**: 불필요한 이미지 삭제 방지
- **병렬 빌드**: `--parallel` 옵션으로 빌드 시간 단축
- **볼륨 재사용**: Python 라이브러리 볼륨 재활용
- **메모리 최적화**: FastAPI 컨테이너 리소스 제한

### 백업 및 복구
```bash
# MySQL 백업
docker-compose exec mysql mysqldump -u root -p760329 dogi > backup.sql

# MongoDB 백업
docker-compose exec mongodb mongodump --authenticationDatabase admin -u root -p 760329

# ChromaDB 볼륨 백업
docker run --rm -v dogi_chroma-data:/data -v $(pwd):/backup ubuntu tar czf /backup/chroma-backup.tar.gz /data

# Python 라이브러리 볼륨 백업
docker run --rm -v dogi_python-libs:/libs -v $(pwd):/backup ubuntu tar czf /backup/libs-backup.tar.gz /libs
```

## 문제 해결

### 일반적인 문제

1. **GPU 메모리 부족**
   - FastAPI 컨테이너 메모리 제한 조정
   - `deploy.resources.limits.memory` 값 증가

2. **라이브러리 설치 실패**
   - `python-libs-init-dogi` 컨테이너 로그 확인
   - CUDA 버전 호환성 확인
   - 볼륨 삭제 후 재설치

3. **데이터베이스 연결 실패**
   - 네트워크 및 환경변수 확인
   - `wait-for-it` 스크립트 대기 시간 조정
   - 서비스 시작 순서 확인

4. **모델 로딩 실패**
   - 모델 파일 경로 및 권한 확인
   - `./fastapi/models/` 디렉토리 권한 설정
   - 모델 파일 크기 및 메모리 요구사항 확인

### 로그 위치 및 확인 방법

```bash
# FastAPI 로그
docker-compose logs fastapi
tail -f ./fastapi/logs/$(date +%Y%m%d).log

# MySQL 로그
docker-compose logs mysql
tail -f ./mysql/logs/error.log

# MongoDB 로그
docker-compose logs mongodb
tail -f ./mongo/logs/mongodb.log

# ChromaDB 로그
docker-compose logs chromadb

# Python 라이브러리 설치 로그
docker-compose logs python-libs-init-dogi
```

### 디버깅 팁

1. **컨테이너 내부 접근**:
   ```bash
   docker-compose exec fastapi bash
   docker-compose exec mysql mysql -u root -p
   docker-compose exec mongodb mongosh
   ```

2. **네트워크 연결 테스트**:
   ```bash
   docker-compose exec fastapi ping mysql
   docker-compose exec fastapi curl chromadb:7999/api/v1/heartbeat
   ```

3. **볼륨 상태 확인**:
   ```bash
   docker volume ls
   docker volume inspect dogi_python-libs
   ```

## 보안 고려사항

1. **환경변수 관리**: `.env` 파일을 Git에서 제외
2. **데이터베이스 보안**: 기본 비밀번호 변경 권장
3. **네트워크 격리**: 프로덕션에서는 내부 네트워크 사용
4. **로그 관리**: 민감한 정보 로그 출력 방지
5. **볼륨 권한**: 적절한 파일 시스템 권한 설정