#!/bin/bash
set -e

TARGET_DIR="/opt/python-libs/lib/python3.11/site-packages"

if [ ! -f /opt/python-libs/.initialized ]; then
    echo "Installing Python libraries to volume..."
    
    # 타겟 디렉토리 생성
    mkdir -p "$TARGET_DIR"
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # 기존 파일 정리 (충돌 방지)
    echo "Cleaning up any existing conflicting installations..."
    rm -rf "$TARGET_DIR"/*
    
    # 기본 requirements 설치
    echo "Installing basic requirements..."
    pip install --target="$TARGET_DIR" \
        -r /app/requirements.txt \
        --no-cache-dir
    
    # numpy 먼저 설치 (다른 패키지들의 의존성) - 버전 고정
    echo "Installing numpy..."
    pip install --target="$TARGET_DIR" "numpy>=1.22.4,<2.3.0" --no-cache-dir
    
    # PyTorch 설치 (CUDA 12.1 버전) - 호환 가능한 버전으로 고정
    echo "Installing PyTorch..."
    pip install --target="$TARGET_DIR" \
        torch==2.3.1+cu121 \
        torchvision==0.18.1+cu121 \
        torchaudio==2.3.1+cu121 \
        -f https://download.pytorch.org/whl/torch_stable.html \
        --no-cache-dir
    
    # CUDA 관련 패키지 설치
    echo "Installing CUDA packages..."
    pip install --target="$TARGET_DIR" \
        -r /app/requirements_llama.txt \
        --no-cache-dir
    
    # llama-cpp-python 설치 (CUDA 지원)
    echo "Installing llama-cpp-python with CUDA support..."
    CMAKE_ARGS="-DGGML_CUDA=ON" pip install --target="$TARGET_DIR" \
        llama-cpp-python==0.2.62 --no-cache-dir --force-reinstall
    
    # 의존성 확인
    echo "Checking installed packages..."
    python3 -c "
import sys
sys.path.insert(0, '$TARGET_DIR')

packages_to_check = [
    ('jwt', 'PyJWT'),
    ('chromadb', 'chromadb'),
    ('torch', 'torch'),
    ('transformers', 'transformers'),
    ('llama_cpp', 'llama-cpp-python'),
    ('fastapi', 'fastapi'),
    ('uvicorn', 'uvicorn'),
    ('passlib', 'passlib')
]

for package, name in packages_to_check:
    try:
        module = __import__(package)
        version = getattr(module, '__version__', 'unknown')
        print(f'✅ {name} {version} installed successfully')
    except ImportError as e:
        print(f'❌ {name} import failed: {e}')
"
    
    # 초기화 완료 마크
    touch /opt/python-libs/.initialized
    echo "Libraries installation completed!"
else
    echo "Libraries already installed, skipping..."
fi