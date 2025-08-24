# v1 API 구성 계획

## LLM 라우터

|메서드|경로|설명|
|---|---|---|
|GET|/v1/llm/models|LLM 모델 목록 조회|
|POST|/v1/llm/sessions|LLM 세션 생성|
|GET|/v1/llm/sessions|LLM 세션 목록 조회|
|GET|/v1/llm/sessions/{session_id}|LLM 세션 입장|
|DELETE|/v1/llm/sessions/{session_id}|LLM 세션 삭제|
|POST|/v1/llm/sessions/{session_id}/messages|LLM 세션에 메시지 추가 (스트리밍)|
|GET|/v1/llm/sessions/{session_id}/messages|LLM 세션 메시지 목록 조회|
|PATCH|/v1/llm/sessions/{session_id}/messages|LLM 세션 마지막 대화 수정 (스트리밍)|
|DELETE|/v1/llm/sessions/{session_id}/messages|LLM 세션 마지막 대화 삭제|
|POST|/v1/llm/sessions/{session_id}/regenerate|LLM 세션 마지막 메시지 재생성 (스트리밍)|

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
- 설명: 새로운 LLM 세션 생성
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
- 설명: LLM 세션에 새로운 메시지 추가 (실시간 스트리밍 응답)
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
  "model_id": "llama3"
}
```

- 200 응답 (스트리밍)
```
Content-Type: text/plain
Cache-Control: no-cache
Connection: keep-alive

강아지가 갑자기 토하고 설사를 하는 것은 여러 가지 원인이 있을 수 있습니다. 이 증상은 급성 심한 질환을 나타낼 수도 있으므로, 즉시 전문가의 상담과 진단이 필요합니다.

우선, 다음과 같은 일반적인 조치를 통해 상황을 확인해보세요:

1. **수분 공급**: 강아지가 탈수를 피하기 위해 충분한 물을 제공하세요.
2. **안전 관리**: 강아지가 토를 하거나 설사하는 동안 안전한 환경을 유지하세요.

이러한 조치 외에도, 다음과 같은 가능성을 고려해야 합니다:

- **감염성 질환**: 염증성 장질환, 파라볼리자이네스 등
- **비소화기 문제**: 간부전, 췌장염 등의 소화기 질환
- **기타 질환**: 급성 심장 질환, 신장 손상 등

강아지가 이와 같은 증상을 보인다면, 가능한 빨리 전문가의 진료를 받도록 하세요. 의사는 정확한 원인을 파악하고 적절한 치료를 제공할 수 있습니다.
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
- 설명: LLM 세션의 마지막 메시지 수정 (실시간 스트리밍 응답)
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
  "content": "강아지가 음식을 잘 못 먹은 것 같아요.",
  "model_id": "llama3"
}
```

- 200 응답 (스트리밍)
```
Content-Type: text/plain
Cache-Control: no-cache
Connection: keep-alive

강아지가 음식을 잘 못 먹은 경우, 우선 강아지의 상태를 주의 깊게 관찰해야 합니다. 만약 강아지가 계속해서 음식을 거부하거나 다른 이상 증상을 보인다면, 즉시 수의사에게 상담하는 것이 좋습니다.

다음과 같은 조치를 취해보세요:

1. **식사량 조절**: 소량씩 자주 먹이기
2. **소화하기 쉬운 음식**: 닭고기와 쌀 등 부드러운 음식 제공
3. **수분 공급**: 충분한 물 제공
4. **관찰**: 24시간 동안 증상 변화 관찰

증상이 지속되거나 악화된다면 즉시 전문의 상담이 필요합니다.
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
- 설명: LLM 세션의 마지막 메시지를 재생성 (실시간 스트리밍 응답)
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
  "model_id": "gpt4o"
}
```

- 200 응답 (스트리밍)
```
Content-Type: text/plain
Cache-Control: no-cache
Connection: keep-alive

강아지의 소화 문제는 다양한 원인이 있을 수 있습니다. 

**즉시 취해야 할 조치:**

1. **금식**: 12-24시간 동안 음식을 중단하되 물은 계속 제공
2. **점진적 식사 재개**: 소량의 닭고기와 쌀로 시작
3. **증상 모니터링**: 구토, 설사, 식욕부진 등 관찰

**수의사 상담이 필요한 경우:**
- 증상이 24시간 이상 지속
- 혈변이나 혈토
- 심한 탈수 증상
- 무기력하거나 반응이 없음

조기 진단과 치료가 중요하므로 의심스러운 증상이 있다면 지체하지 말고 전문의와 상담하세요.
```

## 스트리밍 API 사용법

### 클라이언트 구현 예시 (JavaScript)
```javascript
// fetch API를 사용한 스트리밍 응답 처리
async function sendMessage(sessionId, content, modelId) {
    const response = await fetch(`/v1/llm/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            content: content,
            model_id: modelId
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        // 실시간으로 화면에 텍스트 표시
        displayText(chunk);
    }
}
```

### 에러 처리
스트리밍 중 에러가 발생하면 `[ERROR]` 접두사와 함께 에러 메시지가 전송됩니다:
```
[ERROR] 메시지 추가 중 오류: 연결이 끊어졌습니다.
```