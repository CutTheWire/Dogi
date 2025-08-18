# v1 API 구성 계획

## LLM 라우터

|메서드|경로|설명|
|---|---|---|
|GET|/v1/llm/models|LLM 모델 목록 조회|
|POST|/v1/llm/sessions|LLM 세션 생성|
|GET|/v1/llm/sessions|LLM 세션 목록 조회|
|GET|/v1/llm/sessions/{session_id}|LLM 세션 입장|
|DELETE|/v1/llm/sessions/{session_id}|LLM 세션 삭제|
|POST|/v1/llm/sessions/{session_id}/messages|LLM 세션에 메시지 추가|
|GET|/v1/llm/sessions/{session_id}/messages|LLM 세션 메시지 목록 조회|
|PATCH|/v1/llm/sessions/{session_id}/messages|LLM 세션 마지막 대화 수정|
|DELETE|/v1/llm/sessions/{session_id}/messages|LLM 세션 마지막 대화 삭제|
|POST|/v1/llm/sessions/{session_id}/regenerate|LLM 세션 마지막 메시지 재생성|

### LLM 모델 목록 조회 (GET /v1/llm/models)
- 설명: 사용 가능한 모델 목록

- 200 응답
```JSON
{
  "models": [
    {
      "vendor": "Meta",
      "id": "llama3",
      "name": "Llama 3",
      "description": "성능이 향상된 차세대 Llama 시리즈 언어 모델."
    },
    {
      "vendor": "OpenAI",
      "id": "gpt4o",
      "name": "GPT-4o",
      "description": "텍스트와 멀티모달 처리에 뛰어난 OpenAI의 고성능 언어 모델."
    },
    {
      "vendor": "OpenAI",
      "id": "gpt41",
      "name": "GPT-4.1",
      "description": "고급 추론 능력과 안정성을 갖춘 GPT-4 시리즈의 최신 버전."
    },
    {
      "vendor": "OpenAI",
      "id": "gpt5",
      "name": "GPT-5",
      "description": "추론, 이해, 복잡한 작업 처리 능력이 크게 향상된 차세대 OpenAI 언어 모델."
    },
  ]
}
```

### LLM 세션 생성 (POST /v1/llm/sessions)
- 설명: 
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 요청 본문 없음

- 201 응답
```JSON
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### LLM 세션 목록 조회 (GET /v1/llm/sessions)
- 설명: 현재 활성화된 LLM 세션 목록 조회
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 200 응답
```JSON
{
  "sessions": [
    {
      "session_id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "우리 강아지가 갑자기 토하고 설사를 ...",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:30:00Z"
    },
    {
      "session_id": "123e4567-e89b-12d3-a456-426614174001",
      "title": "강아지 털이 빠지고 가려워해요. 피부...",
      "created_at": "2024-01-02T14:30:00Z",
      "updated_at": "2024-01-02T15:00:00Z"
    }
  ]
}
```

### LLM 세션 입장 (GET /v1/llm/sessions/{session_id})
- 설명: 특정 LLM 세션에 입장하여 대화 시작
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 200 응답
```JSON
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "우리 강아지가 갑자기 토하고 설사를 ...",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:30:00Z"
}
```

### LLM 세션 삭제 (DELETE /v1/llm/sessions/{session_id})
- 설명: 특정 LLM 세션 삭제
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 204 응답
```JSON
{
  "message": "세션이 성공적으로 삭제되었습니다."
}
```

### LLM 세션에 메시지 추가 (POST /v1/llm/sessions/{session_id}/messages)
- 설명: LLM 세션에 새로운 메시지 추가
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 요청 본문
```JSON
{
  "content": "우리 강아지가 갑자기 토하고 설사를 해요.",
  "model id": "llama3"
}
```

- 201 응답
```JSON
{
  "message_idx": "1",
  "answer": "그런 경우 수의사에게 즉시 상담하는 것이 좋습니다. 탈수 증상이 있을 수 있으니 수분을 충분히 공급해 주세요.",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### LLM 세션 메시지 목록 조회 (GET /v1/llm/sessions/{session_id}/messages)
- 설명: 특정 LLM 세션의 메시지 목록 조회
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 200 응답
```JSON
{
  "messages": [
    {
      "message_idx": "1",
      "content": "우리 강아지가 갑자기 토하고 설사를 해요.",
      "answer": "그런 경우 수의사에게 즉시 상담하는 것이 좋습니다. 탈수 증상이 있을 수 있으니 수분을 충분히 공급해 주세요.",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    },
    {
      "message_idx": "2",
      "content": "강아지가 먹은 음식이 이상한 것 같아요.",
      "answer": "음식이 상했거나 강아지가 알레르기가 있을 수 있습니다. 즉시 수의사에게 상담하세요.",
      "created_at": "2024-01-01T12:05:00Z",
      "updated_at": "2024-01-01T12:05:00Z"
    }
  ]
}
```

### LLM 세션 마지막 대화 수정 (PATCH /v1/llm/sessions/{session_id}/messages)
- 설명: LLM 세션의 마지막 메시지 수정
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}| 

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 요청 본문
```JSON
{
  "message_idx": "2",
  "content": "강아지가 음식을 잘 못 먹은 것 같아요.",
  "model id": "llama3"
}
```

- 200 응답
```JSON
{
  "message_idx": "2",
  "answer": "강아지가 음식을 잘 못 먹은 경우, 우선 강아지의 상태를 주의 깊게 관찰해야 합니다. 만약 강아지가 계속해서 음식을 거부하거나 다른 이상 증상을 보인다면, 즉시 수의사에게 상담하는 것이 좋습니다.",
  "created_at": "2024-01-01T12:05:00Z",
  "updated_at": "2024-01-01T12:10:00Z"
}
```

### LLM 세션 마지막 대화 삭제 (DELETE /v1/llm/sessions/{session_id}/messages)
- 설명: LLM 세션의 마지막 메시지 삭제
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 204 응답
```JSON
{
  "message": "마지막 메시지가 성공적으로 삭제되었습니다."
}
```

### LLM 세션 마지막 메시지 재생성 (POST /v1/llm/sessions/{session_id}/regenerate)
- 설명: LLM 세션의 마지막 메시지를 재생성
- 헤더
    |Key|Value|
    |---|---|
    |Authorization|Bearer {access_token}|

- 경로 변수
    |Key|Value|
    |---|---|
    |session_id|세션 ID|

- 요청 본문
```JSON
{
  "content": "어떤 조치를 취해야 할까요?",
  "model_id": "gpt4o",
}
```

- 200 응답
```JSON
{
  "message_idx": "2",
  "awswer": "강아지가 음식을 잘 못 먹은 경우, 우선 강아지의 상태를 주의 깊게 관찰해야 합니다. 만약 강아지가 계속해서 음식을 거부하거나 다른 이상 증상을 보인다면, 즉시 수의사에게 상담하는 것이 좋습니다.",
  "created_at": "2024-01-01T12:15:00Z",
  "updated_at": "2024-01-01T12:15:00Z"
}
```