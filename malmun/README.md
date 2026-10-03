# 말문 English

스픽(Speak)처럼 **직접 소리 내어 말하면서** 배우는 영어 말하기 학습 프로그램입니다.
"말문이 트이다"에서 이름을 따왔습니다.

## 주요 기능

| 기능 | 내용 |
| --- | --- |
| 레슨 (4개 코스 · 12개 레슨 · 72문장) | 일상 회화, 여행, 비즈니스, 연구자 영어(학회 발표·Q&A·네트워킹) |
| 듣고 따라 말하기 | 원어민 음성(TTS)을 듣고 따라 말하면 음성 인식으로 단어별 정확도를 채점합니다. 놓친 단어는 빨간 물결선, 핵심 표현은 형광펜으로 표시됩니다. 0.7배속 듣기도 됩니다. |
| 영어로 말해 보기 | 한국어 문장을 보고 영어로 말하면 AI 코치가 뜻과 문법을 채점하고, 내 표현을 살린 더 나은 문장을 알려 줍니다. |
| AI 튜터 롤플레이 (11개 상황) | 카페, 입국 심사, 호텔, 회의, 면접, 학회 Q&A, 반도체 정책 토론 등. AI가 상대역을 맡아 대화하고, 말할 때마다 "더 자연스러운 표현"과 한국어 설명을 줍니다. 힌트(다음에 할 말 예시)와 해석 보기도 있습니다. |
| 대화 리포트 | 대화를 끝내면 잘한 점, 고쳐 말하기, 이 상황에서 쓸 표현을 정리해 줍니다. |
| 복습 (간격 반복) | 놓친 문장과 저장한 교정 표현을 1·3·7·16일 간격으로 다시 물어봅니다. |
| 학습 기록 | 하루 목표(문장 수), 연속 학습일, XP, 평균 정확도, 최근 5주 학습 달력 |

AI 코치가 꺼져 있어도 레슨, 따라 말하기 채점, 복습은 그대로 쓸 수 있습니다. 이때 "영어로 말해 보기"는 모범 답안과의 단어 비교로 채점합니다.

## 실행 방법

Python 3.10 이상과 Chrome(또는 Edge)이 필요합니다.

```bash
cd malmun
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python server.py
```

Chrome에서 <http://127.0.0.1:8000> 을 열고, 처음 마이크 버튼을 누를 때 마이크 권한을 허용하세요.

설정할 수 있는 환경 변수:

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (없음) | Claude API 키. 없으면 AI 코치 없이 실행됩니다. |
| `MALMUN_MODEL` | `claude-opus-5-5` | AI 코치에 쓸 Claude 모델 |
| `MALMUN_PORT` | `8000` | 서버 포트 |
| `MALMUN_HOST` | `127.0.0.1` | 서버 주소. 서버가 API 키로 요청을 대신 보내므로 외부에 공개하지 마세요. |

## 구조

```
malmun/
├── server.py           # 앱 화면 제공 + Claude API 중계 (FastAPI)
├── static/app.html     # 앱 전체: 레슨 콘텐츠, 음성 인식·합성, 채점, AI 튜터, 복습, 기록
├── requirements.txt
└── tests/test_server.py
```

- **음성**: 브라우저의 Web Speech API를 씁니다. 음성 인식(`SpeechRecognition`)은 Chrome·Edge에서 동작하고, 지원하지 않는 브라우저에서는 자동으로 키보드 입력으로 바뀝니다.
- **발음 채점**: 인식된 문장과 목표 문장을 단어 단위로 맞춰 봅니다(최장 공통 부분열). 축약형(I'm = I am), 숫자(5 = five), 띄어쓰기 차이(check-out = check out), 한두 글자 오인식(Daejeon ≈ dejon)은 맞은 것으로 봅니다.
- **AI 코치**: 모든 AI 요청은 `server.py`의 `/api/claude`를 거쳐 Claude API로 갑니다. 응답은 JSON 스키마로 고정된 구조화 출력이라 화면에 바로 쓸 수 있습니다. 대화와 채점은 응답 속도를 위해 effort `low`, 리포트는 `medium`으로 요청합니다. 프롬프트는 `app.html`의 `tutorSystem`, `gradeRequest`, `reportRequest`에 있습니다.
- **claude.ai 아티팩트로도 동작**: `app.html`은 아티팩트 형식(문서 뼈대 없음)으로 작성되어 있어 그대로 claude.ai에 게시할 수 있습니다. 그곳에서는 로컬 서버 대신 아티팩트의 Claude 호출 기능을 씁니다. 다만 아티팩트 화면에서는 마이크를 쓸 수 없어 키보드 입력으로 연습합니다.

## 개인정보

- 학습 기록과 복습 목록은 이 브라우저의 localStorage에만 저장됩니다.
- Chrome의 음성 인식은 음성을 Google 서버로 보내 텍스트로 바꿉니다.
- AI 코치를 쓰면 대화 내용(텍스트)이 Claude API로 전송됩니다.

## 콘텐츠 바꾸기

레슨은 `app.html`의 `COURSES`, 롤플레이 상황은 `SCENARIOS`에 있습니다. 문장마다 `en`(영어), `ko`(뜻), `key`(형광펜으로 표시할 핵심 표현, 영어 문장에 그대로 들어 있어야 함), `tip`(선택)을 적으면 됩니다.

## 테스트

```bash
pip install pytest
python -m pytest tests
```
