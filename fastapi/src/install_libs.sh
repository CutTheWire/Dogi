#!/bin/bash
set -e

TARGET_DIR="/opt/python-libs/lib/python3.11/site-packages"

if [ ! -f /opt/python-libs/.initialized ]; then
    echo "Installing Python libraries to volume..."
    
    # 타겟 디렉토리 생성
    mkdir -p "$TARGET_DIR"
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # 기본 패키지 먼저 설치
    echo "Installing basic packages..."
    pip install --target="$TARGET_DIR" wheel setuptools
    
    # numpy 먼저 설치 (다른 패키지들의 의존성)
    echo "Installing numpy..."
    pip install --target="$TARGET_DIR" "numpy>=1.22.4,<2.0.0"
    
    # 기본 requirements 설치 (PyTorch 제외)
    echo "Installing basic requirements..."
    pip install --target="$TARGET_DIR" fastapi uvicorn python-dotenv motor pymongo "itsdangerous>=2.0.1" starlette pydantic
    
    # PyTorch 설치 (CUDA 12.1 버전)
    echo "Installing PyTorch..."
    pip install --target="$TARGET_DIR" torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 \
        -f https://download.pytorch.org/whl/torch_stable.html
    
    # Transformers 및 HuggingFace
    echo "Installing transformers..."
    pip install --target="$TARGET_DIR" transformers==4.41.2 huggingface_hub
    
    # LangChain 관련
    echo "Installing LangChain..."
    pip install --target="$TARGET_DIR" langchain langchain_community
    
    # VLLM 설치
    echo "Installing VLLM..."
    pip install --target="$TARGET_DIR" vllm --extra-index-url https://download.pytorch.org/whl/cu121
    
    # llama-cpp-python 빌드 및 설치
    echo "Installing llama-cpp-python..."
    CMAKE_ARGS="-DGGML_CUDA=ON" pip install --target="$TARGET_DIR" llama-cpp-python --no-cache-dir --force-reinstall
    
    # 사전 빌드된 wheel 설치
    echo "Installing pre-built llama-cpp-python wheel..."
    pip install --target="$TARGET_DIR" https://github.com/oobabooga/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui/llama_cpp_python_cuda-0.2.62+cu121-cp311-cp311-manylinux_2_31_x86_64.whl
    
    # 추가 ML 라이브러리 설치
    echo "Installing additional ML libraries..."
    pip install --target="$TARGET_DIR" exllamav2 pynvml
    
    # 초기화 완료 마크
    touch /opt/python-libs/.initialized
    echo "Libraries installation completed!"
else
    echo "Libraries already installed, skipping..."
fi