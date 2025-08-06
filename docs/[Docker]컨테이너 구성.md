[필요 아키텍쳐] : Python-libs, Backed(fastapi), vectorDB(ChromaDB)

1. Python-libs
    > 라이브러리 설치를 위한 베이스 이미지입니다.
   - Python 3.11
   - 설치 라이브러리 (필요 시 게속적인 추가)
      - fastapi
      - uvicorn
      - pydantic
      - chromadb

2. Backed(fastapi)
    > FastAPI를 이용한 백엔드 서버입니다.
   - FastAPI 프레임워크를 사용하여 API 서버 구축
   - 서버 내에서 LLM 모델을 호출하고 응답을 처리
   - LLM 모델
      - OpenAI API
      - Llama 3 8B
  - RAG 구현
      - ChromaDB를 이용한 벡터 데이터베이스 연동
      - 유저의 질문에 대한 벡터 검색 및 응답 생성

3. vectorDB(ChromaDB)
    > ChromaDB를 이용한 벡터 데이터베이스입니다.
   - ChromaDB를 사용하여 벡터 데이터베이스 구축
   - 반려견 성장 및 질병관련 말뭉치 데이터 (AI HUB)를 이용한 벡터 추가