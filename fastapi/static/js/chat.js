// API 기본 설정
const API_BASE_URL = '/v1';

// DOM 요소들
const backBtn = document.getElementById('backBtn');
const sessionsBtn = document.getElementById('sessionsBtn');
const sidebarNewChatBtn = document.getElementById('sidebarNewChatBtn');
const sessionsList = document.getElementById('sessionsList');
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const modelSelect = document.getElementById('modelSelect');
const sessionsModal = document.getElementById('sessionsModal');
const closeSessionsModal = document.getElementById('closeSessionsModal');

// 전역 변수
let currentSessionId = null;
let isStreaming = false;
let currentMessages = []; // 현재 세션의 메시지 목록
let isEditMode = false; // 수정 모드 여부
let originalMessage = ''; // 원본 메시지 저장
let availableModels = []; // 사용 가능한 모델 목록

// 마크다운 설정
marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (err) {}
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true, // 줄바꿈을 <br>로 변환
    gfm: true, // GitHub Flavored Markdown 활성화
});

// 마크다운을 HTML로 변환하는 함수
function parseMarkdown(content) {
    if (!content) return '';
    
    // 마크다운 파싱
    let html = marked.parse(content);
    
    // 코드 블록에 복사 버튼과 언어 표시 추가
    html = html.replace(/<pre><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g, (match, lang, code) => {
        const codeId = 'code-' + Math.random().toString(36).substr(2, 9);
        return `
            <div class="code-header">
                <span class="code-language">${lang}</span>
                <button class="copy-code-btn" onclick="copyCode('${codeId}')">복사</button>
            </div>
            <pre><code id="${codeId}" class="language-${lang}">${code}</code></pre>
        `;
    });
    
    // 언어가 없는 코드 블록도 처리
    html = html.replace(/<pre><code(?! id=)([\s\S]*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
        const codeId = 'code-' + Math.random().toString(36).substr(2, 9);
        return `
            <div class="code-header">
                <span class="code-language">텍스트</span>
                <button class="copy-code-btn" onclick="copyCode('${codeId}')">복사</button>
            </div>
            <pre><code id="${codeId}"${attrs}>${code}</code></pre>
        `;
    });
    
    return html;
}

// 코드 복사 함수
function copyCode(codeId) {
    const codeElement = document.getElementById(codeId);
    if (codeElement) {
        const text = codeElement.textContent;
        navigator.clipboard.writeText(text).then(() => {
            // 복사 성공 피드백
            const button = codeElement.parentElement.parentElement.querySelector('.copy-code-btn');
            const originalText = button.textContent;
            button.textContent = '복사됨!';
            setTimeout(() => {
                button.textContent = originalText;
            }, 2000);
        }).catch(err => {
            console.error('복사 실패:', err);
        });
    }
}

// 모델 목록 로드
async function loadModels() {
    try {
        const response = await apiRequest('/llm/models');
        availableModels = response.models || [];
        
        // 모델 선택 드롭다운 업데이트
        modelSelect.innerHTML = '';
        
        if (availableModels.length === 0) {
            modelSelect.innerHTML = '<option value="">사용 가능한 모델 없음</option>';
            modelSelect.disabled = true;
            return;
        }
        
        // 모델 옵션 추가
        availableModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = `${model.vendor} ${model.model}`;
            modelSelect.appendChild(option);
        });
        
        // 기본 모델 선택 (첫 번째 모델)
        if (availableModels.length > 0) {
            modelSelect.value = availableModels[0].id;
        }
        
        modelSelect.disabled = false;
        
    } catch (error) {
        console.error('Models load error:', error);
        modelSelect.innerHTML = '<option value="">모델 로드 실패</option>';
        modelSelect.disabled = true;
    }
}

// 선택된 모델 ID 가져오기
function getSelectedModel() {
    return modelSelect.value || 'llama3'; // 기본값
}

// URL에서 세션 ID 가져오기
function getSessionIdFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('session');
}

// 토큰 관리
const TokenManager = {
    get: () => {
        return {
            accessToken: localStorage.getItem('access_token'),
            refreshToken: localStorage.getItem('refresh_token')
        };
    },
    
    clear: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },
    
    isLoggedIn: () => {
        return !!localStorage.getItem('access_token');
    }
};

// 모달 제어
const SessionsModalControl = {
    open: () => {
        sessionsModal.classList.add('show');
        document.body.style.overflow = 'hidden';
        loadSessions(); // 모달 열 때마다 세션 목록 새로고침
    },
    
    close: () => {
        sessionsModal.classList.add('hiding');
        setTimeout(() => {
            sessionsModal.classList.remove('show', 'hiding');
            document.body.style.overflow = 'auto';
        }, 300);
    },
    
    handleKeyDown: (event) => {
        if (event.key === 'Escape' && sessionsModal.classList.contains('show')) {
            SessionsModalControl.close();
        }
    }
};

// API 요청 함수 (일반 요청용)
async function apiRequest(url, options = {}) {
    try {
        const tokens = TokenManager.get();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (tokens.accessToken) {
            headers.Authorization = `Bearer ${tokens.accessToken}`;
        }
        
        const response = await fetch(API_BASE_URL + url, {
            headers,
            ...options
        });
        
        if (response.status === 401) {
            TokenManager.clear();
            window.location.href = '/login';
            throw new Error('인증이 만료되었습니다.');
        }
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || '요청 처리 중 오류가 발생했습니다.');
        }
        
        // 204 No Content 응답 처리
        if (response.status === 204) {
            return { message: "성공적으로 처리되었습니다." };
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// 스트리밍 API 요청 함수
async function streamingRequest(url, options = {}) {
    const tokens = TokenManager.get();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (tokens.accessToken) {
        headers.Authorization = `Bearer ${tokens.accessToken}`;
    }
    
    const response = await fetch(API_BASE_URL + url, {
        headers,
        ...options
    });
    
    if (response.status === 401) {
        TokenManager.clear();
        window.location.href = '/login';
        throw new Error('인증이 만료되었습니다.');
    }
    
    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || '요청 처리 중 오류가 발생했습니다.');
    }
    
    return response;
}

// 세션 목록 로드
async function loadSessions() {
    try {
        const response = await apiRequest('/llm/sessions');
        const sessions = response.sessions || [];
        
        sessionsList.innerHTML = '';
        
        if (sessions.length === 0) {
            sessionsList.innerHTML = '<p class="no-sessions">대화 목록이 없습니다.</p>';
            return;
        }
        
        sessions.forEach(session => {
            const sessionElement = document.createElement('div');
            sessionElement.className = 'session-item';
            sessionElement.dataset.sessionId = session.session_id;
            
            if (session.session_id === currentSessionId) {
                sessionElement.classList.add('active');
            }
            
            // title이 있으면 사용하고, 없으면 session_id 일부 사용
            const title = session.title || `대화 ${session.session_id.substring(0, 8)}`;
            const updatedAt = new Date(session.updated_at).toLocaleString('ko-KR');
            
            sessionElement.innerHTML = `
                <div class="session-info">
                    <h4>${title}</h4>
                    <p>${updatedAt}</p>
                </div>
                <button class="session-delete-btn" data-session-id="${session.session_id}" title="삭제">❌</button>
            `;
            
            // 세션 선택 이벤트 (삭제 버튼이 아닌 경우에만)
            sessionElement.addEventListener('click', (e) => {
                if (!e.target.classList.contains('session-delete-btn')) {
                    selectSession(session.session_id);
                    SessionsModalControl.close(); // 세션 선택 후 모달 닫기
                }
            });
            
            // 삭제 버튼 이벤트
            const deleteBtn = sessionElement.querySelector('.session-delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 부모 클릭 이벤트 방지
                deleteSessionDirectly(session.session_id);
            });
            
            sessionsList.appendChild(sessionElement);
        });
        
    } catch (error) {
        console.error('Sessions load error:', error);
    }
}

// 세션 직접 삭제 (모달 없이)
async function deleteSessionDirectly(sessionId) {
    try {
        await apiRequest(`/llm/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        
        if (sessionId === currentSessionId) {
            currentSessionId = null;
            currentMessages = [];
            
            // URL에서 세션 ID 제거
            const newUrl = new URL(window.location);
            newUrl.searchParams.delete('session');
            history.replaceState({}, '', newUrl);
            
            chatMessages.innerHTML = '';
            addWelcomeMessage();
        }
        
        // 세션 목록 새로고침
        await loadSessions();
        
    } catch (error) {
        console.error('Delete session error:', error);
    }
}

// 세션 선택
async function selectSession(sessionId) {
    try {
        // 세션 정보 조회
        const sessionInfo = await apiRequest(`/llm/sessions/${sessionId}`);
        
        currentSessionId = sessionId;
        
        // URL 업데이트
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('session', sessionId);
        history.replaceState({}, '', newUrl);
        
        // UI 업데이트
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('active');
        });
        
        const selectedItem = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('active');
        }
        
        // 메시지 로드
        await loadMessages();
        
    } catch (error) {
        console.error('Session select error:', error);
    }
}

// 메시지 로드
async function loadMessages() {
    if (!currentSessionId) return;
    
    try {
        const response = await apiRequest(`/llm/sessions/${currentSessionId}/messages`);
        currentMessages = response.messages || [];
        
        chatMessages.innerHTML = '';
        
        if (currentMessages.length === 0) {
            // 환영 메시지 표시
            addWelcomeMessage();
        } else {
            currentMessages.forEach((message, index) => {
                // 사용자 메시지 추가
                addMessage(message.content, 'user');
                // AI 응답 추가
                if (message.answer) {
                    const isLastMessage = index === currentMessages.length - 1;
                    addMessage(message.answer, 'ai', false, isLastMessage);
                }
            });
        }
        
        scrollToBottom();
        
    } catch (error) {
        console.error('Messages load error:', error);
    }
}

// 환영 메시지 추가
function addWelcomeMessage() {
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'welcome-message';
    welcomeDiv.innerHTML = `
        <div class="ai-avatar">🐕</div>
        <div class="message-content">
            <p>안녕하세요! 저는 Dogi AI입니다.</p>
            <p>반려견의 건강과 관련된 궁금한 점이 있으시면 언제든 물어보세요.</p>
        </div>
    `;
    chatMessages.appendChild(welcomeDiv);
}

// 메시지 추가
function addMessage(content, type = 'ai', isStreaming = false, showActions = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'user' ? 'user-message' : 'ai-message';
    
    if (type === 'user') {
        messageDiv.innerHTML = `
            <div class="message-content">
                ${parseMarkdown(content)}
            </div>
        `;
    } else {
        const contentHtml = isStreaming ? content : parseMarkdown(content);
        messageDiv.innerHTML = `
            <div class="ai-avatar">🐕</div>
            <div class="message-content">
                ${contentHtml}
            </div>
        `;
        
        // 마지막 AI 메시지에만 액션 버튼 추가
        if (showActions) {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            actionsDiv.innerHTML = `
                <button class="message-action-btn" onclick="regenerateLastMessage()">재생성</button>
                <button class="message-action-btn" onclick="editLastMessage()">수정</button>
                <button class="message-action-btn btn-danger" onclick="deleteLastMessage()">삭제</button>
            `;
            messageDiv.appendChild(actionsDiv);
        }
    }
    
    chatMessages.appendChild(messageDiv);
    
    if (!isStreaming) {
        scrollToBottom();
    }
    
    return messageDiv;
}

// 타이핑 인디케이터 추가
function addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'ai-message typing-indicator';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = `
        <div class="ai-avatar">🐕</div>
        <div class="message-content">
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(typingDiv);
    scrollToBottom();
    
    return typingDiv;
}

// 타이핑 인디케이터 제거
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// 수정 모드 활성화
function editLastMessage() {
    if (currentMessages.length === 0 || isStreaming) return;
    
    isEditMode = true;
    
    // 마지막 사용자 메시지 찾기
    const userMessages = chatMessages.querySelectorAll('.user-message');
    const lastUserMessage = userMessages[userMessages.length - 1];
    
    if (lastUserMessage) {
        const messageContent = lastUserMessage.querySelector('.message-content');
        originalMessage = messageContent.textContent;
        
        // 수정 중 표시
        lastUserMessage.classList.add('editing-message');
        messageContent.innerHTML = '<span class="editing-placeholder">수정 중...</span>';
        
        // 입력창에 원본 메시지 설정
        messageInput.value = originalMessage;
        messageInput.focus();
        
        // 전송 버튼을 재전송으로 변경
        sendBtn.textContent = '재전송';
        sendBtn.classList.add('btn-warning');
    }
}

// 수정 모드 취소
function cancelEditMode() {
    isEditMode = false;
    
    // 수정 중 스타일 제거
    const editingMessage = chatMessages.querySelector('.editing-message');
    if (editingMessage) {
        editingMessage.classList.remove('editing-message');
        const messageContent = editingMessage.querySelector('.message-content');
        messageContent.innerHTML = parseMarkdown(originalMessage);
    }
    
    // 입력창 초기화
    messageInput.value = '';
    
    // 전송 버튼 원래대로
    sendBtn.textContent = '전송';
    sendBtn.classList.remove('btn-warning');
    
    originalMessage = '';
}

// 메시지 전송/재전송
async function sendMessage() {
    const content = messageInput.value.trim();
    const selectedModel = getSelectedModel();
    
    if (!content || isStreaming || !selectedModel) return;
    
    if (isEditMode) {
        // 재전송 모드
        await resendMessage(content, selectedModel);
    } else {
        // 일반 전송 모드
        // 세션이 없으면 새로 생성
        if (!currentSessionId) {
            await createNewSession();
            if (!currentSessionId) return;
        }
        
        // 사용자 메시지 추가
        addMessage(content, 'user');
        messageInput.value = '';
        
        await sendNewMessage(content, selectedModel);
    }
}

// 새 메시지 전송
async function sendNewMessage(content, modelId) {
    // 타이핑 인디케이터 표시
    addTypingIndicator();
    
    try {
        isStreaming = true;
        sendBtn.disabled = true;
        modelSelect.disabled = true;
        
        // 스트리밍 요청
        const response = await streamingRequest(`/llm/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            body: JSON.stringify({
                content: content,
                model_id: modelId
            })
        });
        
        // 타이핑 인디케이터 제거
        removeTypingIndicator();
        
        // AI 응답 메시지 요소 생성 (액션 버튼 포함)
        const aiMessageDiv = addMessage('', 'ai', true, true);
        const messageContent = aiMessageDiv.querySelector('.message-content');
        
        // 스트리밍 응답 처리
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            
            // 에러 체크
            if (chunk.startsWith('[ERROR]')) {
                messageContent.innerHTML = `<p style="color: #dc2626;">${chunk}</p>`;
                break;
            }
            
            fullResponse += chunk;
            // 스트리밍 중에는 마크다운 파싱하지 않고 텍스트만 표시
            messageContent.innerHTML = `<p>${fullResponse.replace(/\n/g, '<br>')}</p>`;
            scrollToBottom();
        }
        
        // 스트리밍 완료 후 마크다운 파싱 적용
        if (!fullResponse.startsWith('[ERROR]')) {
            messageContent.innerHTML = parseMarkdown(fullResponse);
        }
        
        // 메시지 목록 업데이트
        await loadMessages();
        
    } catch (error) {
        removeTypingIndicator();
        console.error('Send message error:', error);
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        modelSelect.disabled = false;
    }
}

// 메시지 재전송
async function resendMessage(content, modelId) {
    // 타이핑 인디케이터 표시
    addTypingIndicator();
    
    try {
        isStreaming = true;
        sendBtn.disabled = true;
        modelSelect.disabled = true;
        
        // 마지막 AI 메시지 제거
        const lastAiMessage = chatMessages.querySelector('.ai-message:last-child');
        if (lastAiMessage && !lastAiMessage.classList.contains('welcome-message')) {
            lastAiMessage.remove();
        }
        
        // 스트리밍 요청 (PATCH 사용)
        const response = await streamingRequest(`/llm/sessions/${currentSessionId}/messages`, {
            method: 'PATCH',
            body: JSON.stringify({
                content: content,
                model_id: modelId,
                message_idx: currentMessages.length
            })
        });
        
        // 타이핑 인디케이터 제거
        removeTypingIndicator();
        
        // AI 응답 메시지 요소 생성 (액션 버튼 포함)
        const aiMessageDiv = addMessage('', 'ai', true, true);
        const messageContent = aiMessageDiv.querySelector('.message-content');
        
        // 스트리밍 응답 처리
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            
            // 에러 체크
            if (chunk.startsWith('[ERROR]')) {
                messageContent.innerHTML = `<p style="color: #dc2626;">${chunk}</p>`;
                break;
            }
            
            fullResponse += chunk;
            // 스트리밍 중에는 마크다운 파싱하지 않고 텍스트만 표시
            messageContent.innerHTML = `<p>${fullResponse.replace(/\n/g, '<br>')}</p>`;
            scrollToBottom();
        }
        
        // 스트리밍 완료 후 마크다운 파싱 적용
        if (!fullResponse.startsWith('[ERROR]')) {
            messageContent.innerHTML = parseMarkdown(fullResponse);
        }
        
        // 수정 모드 종료
        cancelEditMode();
        
        // 메시지 목록 업데이트
        await loadMessages();
        
    } catch (error) {
        removeTypingIndicator();
        console.error('Resend message error:', error);
        cancelEditMode();
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        modelSelect.disabled = false;
    }
}

// 새 세션 생성
async function createNewSession() {
    try {
        const response = await apiRequest('/llm/sessions', {
            method: 'POST'
        });
        
        currentSessionId = response.session_id;
        
        // URL 업데이트
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('session', currentSessionId);
        history.replaceState({}, '', newUrl);
        
        // 메시지 초기화
        chatMessages.innerHTML = '';
        addWelcomeMessage();
        currentMessages = [];
        
        // 모달이 열려있으면 세션 목록 새로고침
        if (sessionsModal.classList.contains('show')) {
            await loadSessions();
            
            // 새 세션 선택
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.remove('active');
            });
            const newSessionItem = document.querySelector(`[data-session-id="${currentSessionId}"]`);
            if (newSessionItem) {
                newSessionItem.classList.add('active');
            }
            
            // 모달 닫기
            SessionsModalControl.close();
        }
        
    } catch (error) {
        console.error('Create session error:', error);
    }
}

// 마지막 메시지 재생성
async function regenerateLastMessage() {
    if (!currentSessionId || currentMessages.length === 0 || isStreaming) return;
    
    const selectedModel = getSelectedModel();
    if (!selectedModel) return;
    
    // 마지막 AI 메시지 제거
    const lastAiMessage = chatMessages.querySelector('.ai-message:last-child');
    if (lastAiMessage && !lastAiMessage.classList.contains('welcome-message')) {
        lastAiMessage.remove();
    }
    
    // 타이핑 인디케이터 표시
    addTypingIndicator();
    
    try {
        isStreaming = true;
        modelSelect.disabled = true;
        
        // 재생성 요청
        const response = await streamingRequest(`/llm/sessions/${currentSessionId}/regenerate`, {
            method: 'POST',
            body: JSON.stringify({
                model_id: selectedModel
            })
        });
        
        // 타이핑 인디케이터 제거
        removeTypingIndicator();
        
        // AI 응답 메시지 요소 생성 (액션 버튼 포함)
        const aiMessageDiv = addMessage('', 'ai', true, true);
        const messageContent = aiMessageDiv.querySelector('.message-content');
        
        // 스트리밍 응답 처리
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            
            // 에러 체크
            if (chunk.startsWith('[ERROR]')) {
                messageContent.innerHTML = `<p style="color: #dc2626;">${chunk}</p>`;
                break;
            }
            
            fullResponse += chunk;
            // 스트리밍 중에는 마크다운 파싱하지 않고 텍스트만 표시
            messageContent.innerHTML = `<p>${fullResponse.replace(/\n/g, '<br>')}</p>`;
            scrollToBottom();
        }
        
        // 스트리밍 완료 후 마크다운 파싱 적용
        if (!fullResponse.startsWith('[ERROR]')) {
            messageContent.innerHTML = parseMarkdown(fullResponse);
        }
        
    } catch (error) {
        removeTypingIndicator();
        console.error('Regenerate error:', error);
    } finally {
        isStreaming = false;
        modelSelect.disabled = false;
    }
}

// 마지막 메시지 삭제
async function deleteLastMessage() {
    if (!currentSessionId || currentMessages.length === 0) return;
    
    try {
        await apiRequest(`/llm/sessions/${currentSessionId}/messages`, {
            method: 'DELETE'
        });
        
        // 메시지 다시 로드
        await loadMessages();
        
    } catch (error) {
        console.error('Delete message error:', error);
    }
}

// 하단으로 스크롤
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 페이지 초기화
async function initializePage() {
    if (!TokenManager.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    
    // 모델 목록 로드
    await loadModels();
    
    const sessionId = getSessionIdFromURL();
    
    if (sessionId) {
        await selectSession(sessionId);
    } else {
        // 기본 환영 메시지 표시
        addWelcomeMessage();
    }
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', () => {
    initializePage();
    
    // 뒤로가기 버튼
    backBtn.addEventListener('click', () => {
        window.location.href = '/';
    });
    
    // 대화목록 모달 열기/닫기
    sessionsBtn.addEventListener('click', SessionsModalControl.open);
    closeSessionsModal.addEventListener('click', SessionsModalControl.close);
    
    // 새 대화 버튼
    sidebarNewChatBtn.addEventListener('click', createNewSession);
    
    // 메시지 전송
    sendBtn.addEventListener('click', sendMessage);
    
    // 엔터 키로 메시지 전송
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
        
        // ESC 키로 수정 모드 취소
        if (e.key === 'Escape' && isEditMode) {
            cancelEditMode();
        }
    });
    
    // 입력 필드 실시간 업데이트 (수정 모드일 때)
    messageInput.addEventListener('input', () => {
        // 입력 필드 자동 크기 조절
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        
        // 수정 모드일 때 실시간으로 사용자 메시지 업데이트
        if (isEditMode) {
            const editingMessage = chatMessages.querySelector('.editing-message');
            if (editingMessage) {
                const messageContent = editingMessage.querySelector('.message-content');
                const inputValue = messageInput.value.trim();
                
                if (inputValue) {
                    messageContent.innerHTML = parseMarkdown(inputValue);
                } else {
                    messageContent.innerHTML = '<span class="editing-placeholder">수정 중...</span>';
                }
            }
        }
    });
    
    // ESC 키로 모달 닫기
    document.addEventListener('keydown', SessionsModalControl.handleKeyDown);
    
    // 모달 외부 클릭 시 닫기
    window.addEventListener('click', (e) => {
        if (e.target === sessionsModal) {
            SessionsModalControl.close();
        }
    });
});
