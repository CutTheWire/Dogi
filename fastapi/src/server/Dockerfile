# 베이스 이미지 설정
FROM dogi-base:latest

# wait-for-it.sh 복사 및 실행 권한 부여
COPY wait-for-it.sh /usr/local/bin/wait-for-it
RUN sed -i 's/\r$//' /usr/local/bin/wait-for-it && chmod +x /usr/local/bin/wait-for-it

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y tzdata netcat-openbsd && \
    ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    echo "Asia/Seoul" > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Seoul

# 애플리케이션 코드만 복사
COPY src/api/ /app/src/api/
COPY src/domain/ /app/src/domain/
COPY src/llm/ /app/src/llm/
COPY src/server/ /app/src/server/
COPY src/service/ /app/src/service/
COPY src/core/ /app/src/core/

# 프롬프트/설정 - 올바른 경로로 수정
COPY prompt/ /app/prompt/

# 환경 설정 (python-libs-init 볼륨 경로 포함)
ENV PYTHONPATH="/opt/python-libs/lib/python3.11/site-packages:/app:/app/src"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# src 디렉토리에서 실행
WORKDIR /app/src

# 서버 실행
CMD ["/usr/local/bin/wait-for-it", "mysql:3306", "--", "python", "server/server.py"]