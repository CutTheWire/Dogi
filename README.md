# 프로젝트 구성원

| 구성원 | 업무 | 사용 기술 |  
|--------|--------|------------|  
| ✅ [서정훈 (CutTheWire)](https://github.com/CutTheWire) | 프로젝트 매니저, 백엔드 | FastAPI, Llama CPP CUDA, LangChain |  

## 👨‍💻 담당 업무
- 전체 시스템 아키텍처 설계
- FastAPI 전체 API 서버 개발
- OpenAI API 연동
- FastAPI Llama 모델 연동
- Vector DB(ChromaDB) 구축 및 반려동물의료 데이터셋 연동

## 🐋 Docker Container 구성
![Dogi_Docker](https://cutwire.myddns.me/media/webp/Dogi_Docker.webp)
```bat
> docker ps -a
CONTAINER ID   IMAGE                    COMMAND                  CREATED        STATUS                      PORTS                               NAMES
8ddbce961a79   dogi-fastapi             "/opt/nvidia/nvidia_…"   29 hours ago   Up 9 minutes               0.0.0.0:80->80/tcp                  fastapi
ba80d10d6aee   dogi-mongodb             "docker-entrypoint.s…"   29 hours ago   Up 9 minutes               0.0.0.0:27017->27017/tcp            dogi-mongodb-1
2db6afbe9ce9   dogi-mysql               "/entrypoint.sh --ch…"   29 hours ago   Up 9 minutes (healthy)     0.0.0.0:3306->3306/tcp, 33060/tcp   dogi-mysql-1
d94500b8b8bb   chromadb/chroma:latest   "dumb-init -- chroma…"   29 hours ago   Up 9 minutes               0.0.0.0:8000->8000/tcp              chromadb
fc46fe7d5ab5   dogi-python-libs-init    "/opt/nvidia/nvidia_…"   29 hours ago   Exited (0) 9 minutes ago          
```

### Docker Compose 파일
```yml
services:
  python-libs-init:
    build:
      context: ./fastapi
      dockerfile: src/Dockerfile.libs
    container_name: python-libs-init
    volumes:
      - python-libs:/opt/python-libs
    command: >
      sh -c "
      if [ ! -f /opt/python-libs/.initialized ]; then
        echo 'Installing Python libraries...'
        pip install --target=/opt/python-libs/lib/python3.11/site-packages 'numpy>=1.22.4,<2.0.0'
        pip install --target=/opt/python-libs/lib/python3.11/site-packages torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 -f https://download.pytorch.org/whl/torch_stable.html
        pip install --target=/opt/python-libs/lib/python3.11/site-packages -r requirements.txt
        CMAKE_ARGS='-DGGML_CUDA=ON' pip install --target=/opt/python-libs/lib/python3.11/site-packages llama-cpp-python --no-cache-dir --force-reinstall
        pip install --target=/opt/python-libs/lib/python3.11/site-packages https://github.com/oobabooga/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui/llama_cpp_python_cuda-0.2.62+cu121-cp311-cp311-manylinux_2_31_x86_64.whl
        pip install --target=/opt/python-libs/lib/python3.11/site-packages exllamav2 pynvml uvicorn
        touch /opt/python-libs/.initialized
        echo 'Libraries installation completed!'
      else
        echo 'Libraries already installed, skipping...'
      fi
      "

  mysql:
    restart: unless-stopped
    build:
      context: ./mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_ROOT_HOST: ${MYSQL_ROOT_HOST}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      TZ: Asia/Seoul  # 한국 시간대 설정
    volumes:
      - ./mysql/data:/var/lib/mysql:rw
      - ./mysql/log.cnf:/etc/mysql/conf.d/log.cnf:ro
      - ./mysql/logs:/var/log/mysql:rw
    command: [
      "--character-set-server=utf8mb4", 
      "--collation-server=utf8mb4_unicode_ci",
      "--skip-host-cache",
      "--skip-name-resolve"
      ]

  chromadb:
    image: chromadb/chroma:latest
    container_name: chromadb
    ports:
      - "8000:8000"
    volumes:
      - chroma-data:/data
    environment:
      - IS_PERSISTENT=TRUE
      - PERSIST_DIRECTORY=/data
      - ANONYMIZED_TELEMETRY=FALSE
    restart: unless-stopped

  mongodb:
    restart: unless-stopped
    build:
      context: ./mongo
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_ADMIN_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ADMIN_PASSWORD}
      MONGO_DATABASE: ${MONGO_DATABASE}
      TZ: Asia/Seoul  # 한국 시간대 설정
    volumes:
      - ./mongo/data:/data/db:rw
      - ./mongo/logs:/var/logs/mongodb:rw
      - ./.env:/docker-entrypoint-initdb.d/.env:ro

  fastapi:
    restart: always
    build:
      context: ./fastapi
      dockerfile: src/server/Dockerfile
    container_name: fastapi
    ports:
      - "80:80"
    volumes:
      - python-libs:/opt/python-libs:ro
      - ./fastapi/models/:/app/fastapi/models/:rw
      - ./fastapi/logs:/app/logs:rw
      - ./fastapi/static:/app/static:ro
      - ./.env:/app/src/.env:ro
    depends_on:
      - python-libs-init
      - chromadb
      - mongodb
      - mysql
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4.0'
        reservations:
          memory: 4G
          devices:
            - driver: nvidia
              capabilities: [gpu]
    environment:
      - TZ=Asia/Seoul  # 한국 시간대 설정
    command: [
      "/usr/local/bin/wait-for-it",
      "mysql:3306", "--",
      "python", "server/server.py"
    ]

volumes:
  python-libs:
    driver: local
  chroma-data:
    driver: local
  mysql-data:
    driver: local
```

## ⚡ FastAPI  디렉토리 구조

<pre data-owner="CutTheWire" data-repo="Dogi" data-folder="fastapi"><code class="language-directory">
 ┣ 📂logs
 ┣ 📂models
 ┃ ┣ 📜gguf_download.py
 ┃ ┗ 📜[llama-3-Korean-Bllossom-8B.gguf](https://huggingface.co/MLP-KTLim/llama-3-Korean-Bllossom-8B-gguf-Q4_K_M)
 ┣ 📂prompt
 ┃ ┣ 📜config-Llama.json
 ┃ ┗ 📜config-OpenAI.json
 ┣ 📂src
 ┃ ┣ 📂api
 ┃ ┃ ┣ 📂v1
 ┃ ┃ ┃ ┣ 📜auth_controller.py
 ┃ ┃ ┃ ┣ 📜llm_controller.py
 ┃ ┃ ┃ ┗ 📜__init__.py
 ┃ ┃ ┣ 📜page_controller.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂core
 ┃ ┃ ┣ 📜app_state.py
 ┃ ┃ ┣ 📜bot_filter.py
 ┃ ┃ ┣ 📜dependencies.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂domain
 ┃ ┃ ┣ 📂models
 ┃ ┃ ┃ ┗ 📜models.json
 ┃ ┃ ┣ 📜base_config.py
 ┃ ┃ ┣ 📜error_tools.py
 ┃ ┃ ┣ 📜model_registry.py
 ┃ ┃ ┣ 📜schema.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂llm
 ┃ ┃ ┣ 📜llama.py
 ┃ ┃ ┣ 📜openai.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂server
 ┃ ┃ ┣ 📜Dockerfile
 ┃ ┃ ┗ 📜server.py
 ┃ ┣ 📂service
 ┃ ┃ ┣ 📜jwt_service.py
 ┃ ┃ ┣ 📜mongo_client.py
 ┃ ┃ ┣ 📜mysql_client.py
 ┃ ┃ ┣ 📜vector_client.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📜bot.yaml
 ┃ ┣ 📜Dockerfile.base
 ┃ ┣ 📜Dockerfile.libs
 ┃ ┗ 📜install_libs.sh
 ┣ 📂static
 ┃ ┣ 📂css
 ┃ ┃ ┣ 📂base
 ┃ ┃ ┃ ┣ 📜reset.css
 ┃ ┃ ┃ ┣ 📜typography.css
 ┃ ┃ ┃ ┗ 📜variables.css
 ┃ ┃ ┣ 📂components
 ┃ ┃ ┃ ┣ 📜buttons.css
 ┃ ┃ ┃ ┣ 📜cards.css
 ┃ ┃ ┃ ┣ 📜forms.css
 ┃ ┃ ┃ ┣ 📜messages.css
 ┃ ┃ ┃ ┗ 📜modals.css
 ┃ ┃ ┣ 📂layout
 ┃ ┃ ┃ ┣ 📜grid.css
 ┃ ┃ ┃ ┣ 📜navigation.css
 ┃ ┃ ┃ ┗ 📜sidebar.css
 ┃ ┃ ┣ 📂utils
 ┃ ┃ ┃ ┣ 📜display.css
 ┃ ┃ ┃ ┣ 📜helpers.css
 ┃ ┃ ┃ ┣ 📜responsive.css
 ┃ ┃ ┃ ┗ 📜spacing.css
 ┃ ┃ ┣ 📜chat.css
 ┃ ┃ ┣ 📜index.css
 ┃ ┃ ┗ 📜login.css
 ┃ ┣ 📂html
 ┃ ┃ ┣ 📜chat.html
 ┃ ┃ ┣ 📜index.html
 ┃ ┃ ┗ 📜login.html
 ┃ ┗ 📂js
 ┃ ┃ ┣ 📜chat.js
 ┃ ┃ ┣ 📜index.js
 ┃ ┃ ┗ 📜login.js
 ┣ 📜.dockerignore
 ┣ 📜requirements.txt
 ┣ 📜requirements_llama.txt
 ┗ 📜wait-for-it.sh
</code></pre>

## 💾 ChromaDB

### 📊 ChromaDB LangChain 미연동 VS 연동 비교 자료
 - 테스트 일시: 2025년 08월 09일 14시 29분
 - 테스트 케이스 수: 8개
 - 모델: llama-3-Korean-Bllossom-8B
  
<div class="project-link-content">
    <a href="/portfolio/reference/dogi/basic_test_results.md" class="project-link-card dark">
        <i class="fas fa-external-link-alt project-link-icon"></i>
        <span class="project-link-text">LangChain 미연동</span>
    </a>
</div>

<div class="project-link-content">
    <a href="/portfolio/reference/dogi/langchain_test_results.md" class="project-link-card dark">
        <i class="fas fa-external-link-alt project-link-icon"></i>
        <span class="project-link-text">LangChain 연동</span>
    </a>
</div>

### 📄 데이터셋 구성
출처 : [AI HUB의 반려견 성장 및 질병관련 말뭉치 데이터](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&aihubDataSe=data&dataSetSn=71879)

 - 말뭉치 데이터 일부 예시
```JSON 
{
  "title": "수의사와 보호자가 함께 보는 반려동물 아틀라스 시리즈- 심장호흡계질환",
  "author": "윤화영 감수",
  "publisher": "(주)범문에듀케이션",
  "department": "내과",
  "disease": "35\n호흡계통의 생리해부\n_Physiological anatomy of the respiratory system\n호흡계통은 공기 중에서 산소(O2)를 가져와 혈액으로 이동시킴으로써 조직에 전반적으로 분배하며, 세포 대사에서 발생한 이산화탄소(CO2)
  를 바깥으로 배출하는 역할을 한다. 호흡계통은 상부기도와 하부기도, 허파(폐), 가슴막으로 이루어져 있다. 허파는 흉강에 의해 보호받고, 가슴안은 복장뼈, 갈비뼈, 척추에 의해 형성된다.\n산소와 이산화탄소 교환\n가스교환은 
  허파꽈리에서 일어나며, 허파꽈리는 공기로부터 들어온 산소를 전달해주고 이산화탄소를 가져가는 모세혈관으로 둘러싸여 있다. 이로 인해 산소가 적고 이산화탄소가 많은 혈액이 오른쪽 심장에서 나와 허파에 전달되고, 산소가 많고 
  이산화탄소가 적은 혈액이 허파에서 나와 왼쪽 심장에 전달됨으로써 생물체 전체에 이 혈액이 분배된다.\n내시경 검사소견 및 생검 조직의 채취\n전신 마취하에서 소아용 내시경(Fusinon Fiberscope FG-100PE, Japan)을 이용해 분문부, 위저부, 유문동 부위등 위전반을 관찰한 결과 유문동 주위에서 출혈과 출혈반을 동반한 명확한 위염상태를 확인 할 수 있었다 (Fig 1A). 위염부위 관찰후 2mm 직경의 내시경 생검조직 겸자(Fusinon\nK1812 RP, Japan)를 이용해 생검조직을 채취하였으며 채취된 위 생검 조직은 Helicobacter 균속 감염 진단을 위한 도말 압착표본 제작과 PCR 분석에 이용하였다."
}
```

 - 질의응답 데이터 일부 예시
```JSON
{
    "meta": {
        "lifeCycle": "노령견", 
        "department": "내과", 
        "disease": "기타"
    }, 
    "qa": {
        "instruction": "너는 반려견의 건강에 대해 해박한 지식을 가진 전문가야. 보호자의 궁금증을 해소해줘.", 
        "input": "안녕하세요. 현재 포메라니안 암컷 두 마리를 기르고 있습니다. 두 강아지 모두 기관지 협착 증상을 앓고 있으며, 이에 따라 약물을 투여하고 있습니다. 그 중 한 마리인 어미견은 11세로, 최근에는 복부가 부풀어 오르는 
        현상을 보이고 있으며, 평소 식욕이 왕성하고 기호식품을 잘 섭취하고 있습니다. 또한, 흥분할 경우에는 혀가 보라색이나 흰색으로 변화하며 호흡이 힘들어하는 모습을 보여주고 있습니다. 이러한 증상이 기관지 문제 때문인지 
        궁금합니다. 또한, 유선에 종양이 있는 상황에서 흥분 시 호흡 곤란을 겪으며 기침을 하는 경향이 있어, 클리닉에서는 수술을 권하지 않았습니다. 이럴 경우 제가 어떤 조치를 취해야 최선일지 알려주시면 감사하겠습니다.", 
        "output": "두 마리 모두 기관지 협착 진단을 받았다니 매우 안타깝습니다. 기관지 협착의 경우, 흥분 시 호흡이 가빠지는 현상이 나타나며, 기도가 좁아지면서 음압이 발생하게 됩니다. 이때 약해진 기관지 근육은 더 이상 버티지 
        못하고 협착이 악화되며, 호흡 곤란이 발생할 수 있습니다. 경우에 따라 심장 질환이 존재하면 폐에 체액이 축적되어 호흡이 어려워질 수 있습니다. 그러나 갑작스럽게 호흡곤란의 증상이 나타난 것으로 보아, 기관지 협착이 주된 
        원인일 가능성이 크다고 판단됩니다. 이러한 두 가지 원인은 청진과 방사선 촬영을 통해 더 정확한 진단을 받는 것이 좋겠습니다. 또한 기관지 협착이 있는 경우, 체중 증가가 호흡을 악화시킬 수 있으므로, 적절한 다이어트를 통해
         체중을 감소시키는 것이 도움이 될 수 있습니다."
    }
}
```

## 💾 MySQL ERD
![Dogi-ERD](https://cutwire.myddns.me/images/ERD-Dogi.webp)

## 💾 MongoDB 채팅 데이터 예시
```JSON
{
  "_id": {
    "$oid": "68ac97b63114e2e54bf0111a"
  },
  "session_id": "e1468124-c904-498a-bc23-ce85a4568d76",
  "title": "우리집 강아지의 피부에 딱지가 생기고 게속 핥아. 어떤 문제가 있는걸까?",
  "messages": [
    {
      "message_idx": "1",
      "content": "우리집 강아지의 피부에 딱지가 생기고 게속 핥아. 어떤 문제가 있는걸까?",
      "model_id": "llama3",
      "answer": "\n\n강아지의 피부에 딱지가 생기고 계속 핥는 것은 여러 가지 문제를 나타낼 수 있습니다. 아래는 몇 가지 가능성을 제시합니다:\n\n1. **알레르기 반응**:\n   - **식이 알레르기**: 강아지가 섭취한 음식에 대한 
      알레르기가 있을 수 있습니다.\n   - **외재 알레르기**: 꽃가루, 먼지 등 환경 요소와의 알레르기에 의할 수도 있습니다.\n\n2. **피부 질환**:\n   - **모공염** (Acne): 모공이 막히면서 딱지가 생길 수 있습니다.\n   - 
      **진드기 감염**: 진드기가 피부에 자라면서 딱지를 형성할 수 있습니다.\n\n3. **감염**:\n   - **피부 감염**: 박테리아나 곰팡이로 인해 발생할 수 있습니다.\n\n4. **기타 문제**:\n   - **환경적 요인**: 건조한 기후, 
      오래된毛표지 등 환경적인 요인이 영향을 미칠 수 있습니다.\n   - **건강 상태**: 특정 질환(예: 당뇨병)으로 인해 피부 건강이 악화될 수 있습니다.\n\n**대응 방안**:\n1. **의료 진단**: 강아지의 병원을 방문하여 전문가로부터 
      정밀한 진단을 받으시기 바랍니다.\n2. **치사 관리**: 알레르기가 의심되는 경우, 식이를 조정하고 치사 관리를 철저히 하세요.\n3. **피부 관리**: 피부 건강을 유지하기 위해 충분한 휴식을 취하고, 적절한 영양 섭취를 권장합니다.
      \n\n**추가 질문이 있으면 언제든지 말씀해 주세요!**",
      "created_at": {
        "$date": "2025-08-26T02:05:08.844Z"
      },
      "updated_at": {
        "$date": "2025-08-26T02:05:08.844Z"
      }
    },
    {
      "message_idx": "2",
      "content": "병원에 가기전에 어떤 조치를 취하는게 좋을까?",
      "model_id": "llama3",
      "answer": "\n\n강아지가 병원에 가기 전에 취할 수 있는 몇 가지 조치가 있습니다. 아래는 그 중 일부입니다:\n\n1. **의료 기록 확인**:\n   - 강아지의 현재 건강 상태와 과거 질병, 알레르기 등을 기록해 두세요.\n   - 임시로 
      작성된 의료 기록을 복사하여 병원에 가져오세요.\n\n2. **사진 및 영상 데이터**:\n   - 최근 촬영한 사진이나 비디오를 준비하세요. 이는 진단과 치료 과정에서 유용할 수 있습니다.\n\n3. **질병 현황 보고**:\n   - 강아지의 
      현재 증상(예: 기침, 소화기 문제, 피부 문제 등)을 상세하게 기록하고 병원에 가져오세요.\n   - 증상을 기록하기 위해 일기를 작성하는 것도 도움이 될 수 있습니다.\n\n4. **약물 사용 여부**:\n   - 강아지가 현재 복용 중인 
      약물과 용량을 기록하세요.\n   - 의사에게 알려야 할 추가 정보가 있다면 준비하세요.\n\n5. **질문 준비**:\n   - 병원에서 문의할 예정인 질문을 미리 작성하여 준비하세요. 예를 들어, 증상의 원인, 치료 옵션, 회복 기간 등이 
      포함될 수 있습니다.\n\n6. **의사 추천**:\n   - 권위 있는 동물 의학 전문가 추천을 받은 경우, 병원 방문 시 이를 준비해 두세요.\n\n이러한 조치들은 병원 방문 전에 중요한 정보를 제공하고, 진단과 치료 과정에서 시간과 
      노력을 절약할 수 있게 합니다.",
      "created_at": {
        "$date": "2025-08-26T02:05:22.870Z"
      },
      "updated_at": {
        "$date": "2025-08-26T02:05:22.870Z"
      }
    },
    {
      "message_idx": "3",
      "content": "모공염 (Acne)에 대해서 설명해줘.",
      "model_id": "gpt41",
      "answer": "네, 강아지의 **모공염(Acne)**에 대해 알려드리겠습니다.\n\n### 모공염(강아지 여드름)이란?\n모공염은 주로 **수염 부위(턱, 입 주변)**에 발생하는 피부 염증 질환입니다. 강아지의 피부에서 모낭(털이 자라는 구멍)
      에 염증이 생기면서 붉은 뾰루지, 검은 딱지, 농포 등이 생길 수 있으며, 감염이 심하면 고름이 나올 수도 있습니다.\n\n### 주요 증상\n- 턱, 입 주변 피부의 붉음, 뾰루지\n- 작은 고름집(농포), 검은 딱지\n- 강아지가 해당 
      부위를 자주 핥거나 긁음\n- 심한 경우 통증, 부위가 붓고 탈모가 동반되기도 함\n\n### 원인\n- 주로 **호르몬 변화** (특히 1~2년 이하의 어린 강아지에서 잘 나타남)\n- 위생 상태 불량 (음식, 장난감 등에 의한 세균 감염)\n- 
      플라스틱 그릇 사용이 모공염과 연관될 수 있음\n- 털이 빽빽하거나 기름(지방)이 많은 피부\n\n### 치료 및 관리\n- 감염된 부위를 **청결히 관리**하고, 따뜻한 물수건으로 닦아 주세요.\n- 플라스틱 그릇 대신 스테인리스나 도자기 
      그릇으로 교체하면 도움이 될 수 있습니다.\n- 수시로 침구, 장난감, 식기 등을 소독하세요.\n- 상태가 심하거나 염증이 계속된다면 동물병원을 방문하여 항생제 연고, 소독제, 필요 시 먹는 약 처방을 받게 됩니다.\n\n### 
      주의사항\n- 집에서 무리하게 짜거나 만지면 2차 감염 위험이 있습니다.\n- 증상이 심해지거나, 출혈·고름이 많거나, 식욕 저하 등 전신 증상이 함께하면 바로 병원에 데려가야 합니다.\n\n추가적인 궁금증이 있으시거나, 증상 사진을 
      보내주실 수 있다면 더 자세하게 안내해 드릴 수 있습니다.",
      "created_at": {
        "$date": "2025-08-26T02:05:44.188Z"
      },
      "updated_at": {
        "$date": "2025-08-26T02:06:00.671Z"
      }
    }
  ],
  "created_at": {
    "$date": "2025-08-26T02:04:54.068Z"
  },
  "updated_at": {
    "$date": "2025-08-26T02:06:00.671Z"
  }
}
```
