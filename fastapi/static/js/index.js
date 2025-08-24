// API 기본 설정
const API_BASE_URL = '/v1';

// DOM 요소들
const loginBtn = document.getElementById('loginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const profileBtn = document.getElementById('profileBtn');
const startChatBtn = document.getElementById('startChatBtn');
const profileModal = document.getElementById('profileModal');
const profileContent = document.getElementById('profileContent');
const closeBtn = document.querySelector('.close');

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

// API 요청 함수
async function apiRequest(url, options = {}) {
    try {
        const tokens = TokenManager.get();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (tokens.accessToken) {
            headers['Authorization'] = `Bearer ${tokens.accessToken}`;
        }
        
        const response = await fetch(API_BASE_URL + url, {
            headers,
            ...options
        });
        
        if (response.status === 401) {
            // 토큰이 만료된 경우 로그인 페이지로 리다이렉트
            TokenManager.clear();
            updateUI();
            return;
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || '요청 처리 중 오류가 발생했습니다.');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// UI 상태 업데이트
function updateUI() {
    const isLoggedIn = TokenManager.isLoggedIn();
    
    if (isLoggedIn) {
        loginBtn.classList.add('hidden');
        logoutBtn.classList.remove('hidden');
        profileBtn.classList.remove('hidden');
        startChatBtn.textContent = 'AI 상담 시작하기';
    } else {
        loginBtn.classList.remove('hidden');
        logoutBtn.classList.add('hidden');
        profileBtn.classList.add('hidden');
        startChatBtn.textContent = '로그인 후 이용하기';
    }
}

// 로그아웃 처리
async function handleLogout() {
    try {
        const tokens = TokenManager.get();
        if (tokens.refreshToken) {
            // 서버에 로그아웃 요청
            await apiRequest('/auth/logout', {
                method: 'POST',
                body: JSON.stringify({
                    refresh_token: tokens.refreshToken
                })
            });
        }
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // 로컬 토큰 제거
        TokenManager.clear();
        updateUI();
    }
}

// 프로필 조회
async function loadProfile() {
    try {
        const profile = await apiRequest('/auth/profile');
        
        if (!profile) {
            return;
        }
        
        profileContent.innerHTML = `
            <div class="profile-info">
                <div class="profile-field">
                    <label>사용자 ID:</label>
                    <span>${profile.user_id}</span>
                </div>
                <div class="profile-field">
                    <label>이메일:</label>
                    <span>${profile.email}</span>
                </div>
                <div class="profile-field">
                    <label>이름:</label>
                    <span>${profile.full_name}</span>
                </div>
                ${profile.phone ? `
                <div class="profile-field">
                    <label>전화번호:</label>
                    <span>${profile.phone}</span>
                </div>
                ` : ''}
                ${profile.birth_date ? `
                <div class="profile-field">
                    <label>생년월일:</label>
                    <span>${profile.birth_date}</span>
                </div>
                ` : ''}
                ${profile.gender ? `
                <div class="profile-field">
                    <label>성별:</label>
                    <span>${profile.gender === 'M' ? '남성' : profile.gender === 'F' ? '여성' : '기타'}</span>
                </div>
                ` : ''}
                <div class="profile-field">
                    <label>가입일:</label>
                    <span>${new Date(profile.created_at).toLocaleString()}</span>
                </div>
                <div class="profile-field">
                    <label>마지막 로그인:</label>
                    <span>${profile.last_login ? new Date(profile.last_login).toLocaleString() : '정보 없음'}</span>
                </div>
            </div>
        `;
        
        profileModal.style.display = 'block';
        
    } catch (error) {
        console.error('Profile load error:', error);
    }
}

// 채팅 시작
async function startChat() {
    if (!TokenManager.isLoggedIn()) {
        window.location.href = '/login';
        return;
    }
    
    try {
        // 새 세션 생성
        const session = await apiRequest('/llm/sessions', {
            method: 'POST'
        });
        
        // 채팅 페이지로 이동
        window.location.href = `/chat?session=${session.session_id}`;
        
    } catch (error) {
        console.error('Start chat error:', error);
    }
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', () => {
    updateUI();
    
    // 로그인 버튼
    loginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.href = '/login';
    });
    
    // 로그아웃 버튼
    logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleLogout();
    });
    
    // 프로필 버튼
    profileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        loadProfile();
    });
    
    // 채팅 시작 버튼
    startChatBtn.addEventListener('click', (e) => {
        e.preventDefault();
        startChat();
    });
    
    // 모달 닫기 버튼
    closeBtn.addEventListener('click', () => {
        profileModal.style.display = 'none';
    });
    
    // 모달 외부 클릭 시 닫기
    window.addEventListener('click', (e) => {
        if (e.target === profileModal) {
            profileModal.style.display = 'none';
        }
    });
});
