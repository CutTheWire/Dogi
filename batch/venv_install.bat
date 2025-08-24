@echo off
chcp 65001
SETLOCAL

:: pip 최신 버전으로 업그레이드
python.exe -m pip install --upgrade pip

:: numpy 버전 충돌 해결을 위해 먼저 설치
pip install "numpy>=1.22.4,<2.0.0"

:: CUDA 관련 패키지 설치 (torch 먼저)
pip install torch==2.3.1+cu118 torchvision==0.18.1+cu118 torchaudio==2.3.1+cu118 -f https://download.pytorch.org/whl/torch_stable.html

:: CUDA 빌드 도구 설치 (flash-attn보다 먼저)
pip install ninja

:: CUDA llama-cpp 설치 (환경변수 설정)
set CMAKE_ARGS=-DLLAMA_CUBLAS=on
set FORCE_CMAKE=1
pip install --no-cache-dir "https://github.com/oobabooga/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui/llama_cpp_python_cuda-0.3.6+cu121-cp311-cp311-win_amd64.whl"

:: ExLlamaV2 설치
pip install exllamav2==0.2.8

:: Flash Attention 설치 (Windows에서 빌드 문제가 있을 수 있으므로 시도만)
echo Flash Attention 설치를 시도합니다 (실패할 수 있음)...
pip install --no-cache-dir flash-attn==2.3.3 --no-build-isolation || echo Flash Attention 설치 실패 - 건너뜀

:: ChromaDB와 sentence-transformers 설치
pip install chromadb sentence-transformers

:: opencv 버전 충돌 해결
pip install --upgrade "opencv-python-headless>=4.5.0,<4.10.0"

:: 나머지 requirements.txt 패키지 설치
if exist ".\fastapi\requirements.txt" (
    pip install -r .\fastapi\requirements.txt
) else (
    echo requirements.txt 파일을 찾을 수 없습니다.
)

if exist ".\fastapi\requirements_llama.txt" (
    pip install -r .\fastapi\requirements_llama.txt
) else (
    echo requirements_llama.txt 파일을 찾을 수 없습니다.
)

echo.
echo 설치가 완료되었습니다.
echo Flash Attention이 설치되지 않았다면 정상입니다 (Windows에서 빌드 문제가 있을 수 있음).
echo.
ENDLOCAL
