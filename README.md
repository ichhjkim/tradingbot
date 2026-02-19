# 🚀 Upbit Trading Bot Project

업비트(Upbit) API를 활용한 가상화폐 자동매매 봇 프로젝트입니다. 변동성 돌파 전략부터 RSI + 볼린저 밴드 기반의 스마트 DCA 전략까지 다양한 알고리즘을 포함하고 있습니다.

## 📌 주요 특징
- **다양한 전략 지원**: 
    - `bot.py`: 기본 변동성 돌파 전략 + MA5 필터
    - `bot2.py`: RSI + 볼린저 밴드 기반 저점 매수 전략
    - `bot3.py`: Smart DCA(분할 매수) + 패닉 셀 대응 전략
    - `bot4.py`: **Ultimate Survival Edition** (횡보장/상승장 맞춤형 목표 설정 및 실시간 평단가 기반 익절/손절)
- **실시간 알림**: 텔레그램 연동을 통한 매수/매도 및 상태 알림
- **자동화 관리**: PM2를 활용한 24시간 중단 없는 운용
- **안정성**: 9시 장 시작 시 자산 리셋 및 종목별 일일 거래 제한 로직 포함

## 🛠 설치 및 시작하기

### 1. 요구 사항
- Python 3.8+
- 업비트 API Key (Open API 가이드 참조)
- 텔레그램 봇 토큰 및 Chat ID (선택 사항)

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 본인의 정보를 입력합니다.
```env
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. 봇 실행
가장 최신 버전인 `bot4.py` 실행을 권장합니다.
```bash
# 단순 실행
python bot4.py

# PM2를 이용한 백그라운드 실행
pm2 start bot4.py --name "trading-bot"
```

## 📈 전략 설명 (Bot4 기준)
- **매수 타점**: RSI가 30 이하이거나 볼린저 밴드 하단을 돌파하는 과매도 구간 포착 시 진입
- **익절/손절**: 
    - 횡보/하락장: +0.7% 익절
    - 상승장: +1.5% 익절
    - 절대 손절선: -2.8% (강제 대응)
- **일일 제한**: 각 코인당 하루에 단 한 번의 익절만 수행하여 안정적인 수익 확보

## ⚠️ 주의 사항
- 본 소프트웨어는 투자 조언을 제공하지 않습니다. 모든 투자의 책임은 사용자 본인에게 있습니다.
- API Key의 권한 설정 시 '입출금' 권한은 제외하고 '조회' 및 '주문' 권한만 부여하는 것을 강력히 권장합니다.

## 📄 License
MIT License
