#!/bin/bash
set -e

TARGET_DIR="/opt/python-libs/lib/python3.11/site-packages"

if [ ! -f /opt/python-libs/.initialized ]; then
    echo "Installing Python libraries to volume..."
    
    # 타겟 디렉토리 생성
    mkdir -p "$TARGET_DIR"
    
    # numpy 먼저 설치 (다른 패키지들의 의존성)
    echo "Installing numpy..."
    pip install --target="$TARGET_DIR" "numpy>=1.22.4,<2.0.0"
    
    # PyTorch 설치 (CUDA 12.1 버전)
    echo "Installing PyTorch..."
    pip install --target="$TARGET_DIR" torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 \
        -f https://download.pytorch.org/whl/torch_stable.html
    
    # 기본 requirements 설치
    echo "Installing basic requirements..."
    pip install --target="$TARGET_DIR" -r /app/requirements.txt
    
    # llama-cpp-python 빌드 및 설치
    echo "Installing llama-cpp-python..."
    CMAKE_ARGS="-DGGML_CUDA=ON" pip install --target="$TARGET_DIR" llama-cpp-python --no-cache-dir --force-reinstall
    
    # requirements_llama.txt의 패키지들 설치
    echo "Installing LLAMA requirements..."
    pip install --target="$TARGET_DIR" -r /app/requirements_llama.txt
    
    # 초기화 완료 마크
    touch /opt/python-libs/.initialized
    echo "Libraries installation completed!"
else
    echo "Libraries already installed, skipping..."
fi