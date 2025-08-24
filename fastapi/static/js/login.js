// API 기본 설정
const API_BASE_URL = '/v1';

// DOM 요소들
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const registerModal = document.getElementById('registerModal');
const registerLink = document.getElementById('registerLink');
const closeBtn = document.getElementById('closeBtn');
const cancelBtn = document.getElementById('cancelBtn');

// 토큰 관리
const TokenManager = {
    set: (accessToken, refreshToken) => {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
    },
    
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

// 모달 제어 함수
const ModalControl = {
    open: () => {
        registerModal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // 배경 스크롤 방지
        // 첫 번째 입력 필드에 포커스
        setTimeout(() => {
            document.getElementById('reg_user_id').focus();
        }, 100);
    },
    
    close: () => {
        registerModal.style.display = 'none';
        document.body.style.overflow = 'auto'; // 배경 스크롤 복원
        // 폼 리셋
        registerForm.reset();
        // 010 값 복원
        document.getElementById('reg_phone1').value = '010';
    },
    
    // ESC 키로 닫기
    handleKeyDown: (event) => {
        if (event.key === 'Escape' && registerModal.style.display === 'block') {
            ModalControl.close();
        }
    }
};

// API 요청 함수
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(API_BASE_URL + url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
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

// 로그인 처리
async function handleLogin(event) {
    event.preventDefault();
    
    const formData = new FormData(loginForm);
    const loginData = {
        user_id: formData.get('user_id'),
        password: formData.get('password')
    };
    
    try {
        const response = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify(loginData)
        });
        
        // 토큰 저장 (백엔드 응답 구조에 맞게 수정)
        if (response.tokens && response.tokens.access_token && response.tokens.refresh_token) {
            TokenManager.set(response.tokens.access_token, response.tokens.refresh_token);
        }
        
        // 메인 페이지로 이동
        window.location.href = '/';
        
    } catch (error) {
        console.error('Login error:', error);
        alert('로그인에 실패했습니다. 다시 시도해주세요.');
    }
}

// 회원가입 처리
async function handleRegister(event) {
    event.preventDefault();
    
    const formData = new FormData(registerForm);
    
    // 필수 필드 검증
    const requiredFields = ['user_id', 'email', 'password', 'full_name'];
    for (const field of requiredFields) {
        if (!formData.get(field)) {
            alert(`${getFieldLabel(field)}은(는) 필수 입력 항목입니다.`);
            return;
        }
    }
    
    // 사용자 ID 유효성 검증
    const user_id = formData.get('user_id');
    if (!/^[a-zA-Z0-9_]+$/.test(user_id)) {
        alert('사용자 ID는 영문, 숫자, 언더스코어만 사용 가능합니다.');
        return;
    }
    if (user_id.length < 3 || user_id.length > 50) {
        alert('사용자 ID는 3자 이상 50자 이하여야 합니다.');
        return;
    }
    const reservedIds = ['admin', 'root', 'system', 'user', 'test', 'guest'];
    if (reservedIds.includes(user_id.toLowerCase())) {
        alert('사용할 수 없는 사용자 ID입니다.');
        return;
    }
    
    // 이메일 형식 검증
    const email = formData.get('email');
    if (!isValidEmail(email)) {
        alert('올바른 이메일 형식을 입력해주세요.');
        return;
    }
    
    // 비밀번호 강도 검증
    const password = formData.get('password');
    if (!isValidPassword(password)) {
        alert('비밀번호는 8자 이상이어야 하며, 대문자, 소문자, 숫자, 특수문자를 모두 포함해야 합니다.');
        return;
    }
    
    const registerData = {
        user_id: formData.get('user_id'),
        email: formData.get('email'),
        password: formData.get('password'),
        full_name: formData.get('full_name')
    };
    
    // 전화번호 조합 (세 개의 입력 필드에서)
    const phone1 = formData.get('phone1');
    const phone2 = formData.get('phone2');
    const phone3 = formData.get('phone3');
    
    if (phone1 && phone2 && phone3) {
        // 전화번호 유효성 검증
        if (phone1 !== '010') {
            alert('전화번호는 010으로 시작해야 합니다.');
            return;
        }
        if (!/^\d{4}$/.test(phone2)) {
            alert('전화번호 중간 자리는 4자리 숫자여야 합니다.');
            return;
        }
        if (!/^\d{4}$/.test(phone3)) {
            alert('전화번호 마지막 자리는 4자리 숫자여야 합니다.');
            return;
        }
        
        registerData.phone = `${phone1}-${phone2}-${phone3}`;
    }
    
    const birth_date = formData.get('birth_date');
    if (birth_date) {
        registerData.birth_date = birth_date;
    }
    
    const gender = formData.get('gender');
    if (gender) {
        // 백엔드 GenderEnum에 맞게 변환
        const genderMap = {
            'male': 'M',
            'female': 'F',
            'other': 'O'
        };
        registerData.gender = genderMap[gender] || gender;
    }
    
    try {
        const response = await apiRequest('/auth/register', {
            method: 'POST',
            body: JSON.stringify(registerData)
        });
        
        // 회원가입 성공 시 자동으로 토큰 저장 (백엔드 응답 구조에 맞게 수정)
        if (response.tokens && response.tokens.access_token && response.tokens.refresh_token) {
            TokenManager.set(response.tokens.access_token, response.tokens.refresh_token);
        }
        
        // 모달 닫기
        ModalControl.close();
        
        // 메인 페이지로 이동
        window.location.href = '/';
        
    } catch (error) {
        console.error('Register error:', error);
        alert('회원가입에 실패했습니다. 다시 시도해주세요.');
    }
}

// 유효성 검증 함수들
function getFieldLabel(fieldName) {
    const labels = {
        'user_id': '사용자 ID',
        'email': '이메일',
        'password': '비밀번호',
        'full_name': '이름'
    };
    return labels[fieldName] || fieldName;
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function isValidPassword(password) {
    // 백엔드 스키마 요구사항에 맞게 수정: 최소 8자, 대문자, 소문자, 숫자, 특수문자 포함
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);
    const isLongEnough = password.length >= 8;
    
    return hasUpperCase && hasLowerCase && hasNumbers && hasSpecialChar && isLongEnough;
}

// 페이지 로드 시 로그인 상태 확인
function checkLoginStatus() {
    if (TokenManager.isLoggedIn()) {
        // 이미 로그인되어 있으면 메인 페이지로 리다이렉트
        window.location.href = '/';
    }
}

// 전화번호 입력 필드 자동 이동
function setupPhoneInputs() {
    const phone1 = document.getElementById('reg_phone1');
    const phone2 = document.getElementById('reg_phone2');
    const phone3 = document.getElementById('reg_phone3');
    
    if (phone1 && phone2 && phone3) {
        // phone2에서 4자리 입력 시 phone3로 이동
        phone2.addEventListener('input', function() {
            // 숫자만 입력 허용
            this.value = this.value.replace(/[^0-9]/g, '');
            if (this.value.length === 4) {
                phone3.focus();
            }
        });
        
        // phone3에서 숫자만 입력 허용
        phone3.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
        
        // 백스페이스 시 이전 필드로 이동
        phone2.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && this.value.length === 0) {
                phone1.focus();
            }
        });
        
        phone3.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && this.value.length === 0) {
                phone2.focus();
            }
        });
    }
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
    setupPhoneInputs();
    
    // 로그인 폼 이벤트
    loginForm.addEventListener('submit', handleLogin);
    
    // 회원가입 폼 이벤트
    registerForm.addEventListener('submit', handleRegister);
    
    // 회원가입 링크 클릭
    registerLink.addEventListener('click', (e) => {
        e.preventDefault();
        ModalControl.open();
    });
    
    // 모달 닫기 버튼들
    if (closeBtn) closeBtn.addEventListener('click', ModalControl.close);
    if (cancelBtn) cancelBtn.addEventListener('click', ModalControl.close);
    
    // ESC 키로 모달 닫기
    document.addEventListener('keydown', ModalControl.handleKeyDown);
});
