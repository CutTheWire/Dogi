import os
import requests
from pathlib import Path

def download_gguf_model():
    """QuantFactory Meta-Llama-3.1-8B-Claude GGUF 모델을 다운로드합니다."""
    
    url = "https://huggingface.co/QuantFactory/Meta-Llama-3.1-8B-Claude-GGUF/resolve/main/Meta-Llama-3.1-8B-Claude.Q4_0.gguf"
    
    models_dir = Path("./fastapi/models")
    models_dir.mkdir(exist_ok=True)
    
    file_path = models_dir / "Meta-Llama-3.1-8B-Claude.Q4_0.gguf"
    
    if file_path.exists():
        print(f"Model already exists at: {file_path}")
        return str(file_path)
    
    print(f"Downloading model from: {url}")
    print(f"Saving to: {file_path}")
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        print(f"\n이 모델은 약 {total_size}입니다. 다운로드에 시간이 걸릴 수 있습니다...\n")
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)", end="")
        
        print(f"\nDownload completed: {file_path}")
        return str(file_path)
        
    except Exception as e:
        print(f"Download failed: {e}")
        if file_path.exists():
            file_path.unlink()
        return None

if __name__ == "__main__":
    download_gguf_model()