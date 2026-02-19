import time
import pyupbit
import datetime
import pandas as pd
from dotenv import load_dotenv
import os
import logging
import requests

# [최종병기 bot3.5] 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_final.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 감시 대상 (원하시는 대로 수정 가능)
TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
last_report_date = None 

def send_telegram(message):
    """텔레그램 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🤖 [Bot3.5-Survivor]\n{message}"}
    try:
        requests.get(url, params=params)
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e}")

def get_indicators(ticker):
    """지표 계산 (15분봉 기준 + 하락장 필터)"""
    try:
        df = pyupbit.get_ohlcv(ticker, interval="minute15", count=100)
        if df is None or df.empty: return None
        
        # [안전장치] 60분봉 20일 이평선으로 대추세 확인 (역배열 매수 방지)
        df_60 = pyupbit.get_ohlcv(ticker, interval="minute60", count=40)
        ma20_60 = df_60['close'].rolling(window=20).mean().iloc[-1]
        is_falling_market = df['close'].iloc[-1] < ma20_60
        
        # RSI 계산
        delta = df['close'].diff()
        ups, downs = delta.copy(), delta.copy()
        ups[ups < 0], downs[downs > 0] = 0, 0
        period = 14
        au = ups.ewm(com=period-1, min_periods=period).mean()
        ad = downs.abs().ewm(com=period-1, min_periods=period).mean()
        rsi = 100 - (100 / (1 + au / ad))
        
        # 볼린저 밴드
        ma20 = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        upper_band = ma20 + (std * 2)
        lower_band = ma20 - (std * 2)
        
        # 변동성 기반 동적 익절 목표
        bandwidth = (upper_band.iloc[-1] - lower_band.iloc[-1]) / ma20.iloc[-1] * 100
        # 장이 조용하면 1.2%, 변동성이 크면 최대 3.5%까지 익절 목표 상향
        dynamic_target = max(1.2, min(3.5, bandwidth * 0.7))
        
        return {
            "current_price": df['close'].iloc[-1],
            "rsi": rsi.iloc[-1],
            "lower_band_safety": lower_band.iloc[-1] * 1.005, # 0.5% 유격으로 진입 빈도 확보
            "dynamic_target": dynamic_target,
            "is_falling_market": is_falling_market
        }
    except Exception as e:
        logging.error(f"지표 계산 오류: {e}")
        return None

def get_balance_info(ticker):
    """코인 잔고 및 평단가 조회"""
    try:
        balances = upbit.get_balances()
        symbol = ticker.split("-")[1]
        for b in balances:
            if b['currency'] == symbol:
                return {"balance": float(b['balance']), "avg_buy_price": float(b['avg_buy_price'])}
        return {"balance": 0, "avg_buy_price": 0}
    except: return {"balance": 0, "avg_buy_price": 0}

def get_total_equity():
    """총 자산 가치(KRW) 계산"""
    try:
        balances = upbit.get_balances()
        total = 0
        for b in balances:
            if b['currency'] == "KRW":
                total += float(b['balance']) + float(b['locked'])
            else:
                price = pyupbit.get_current_price(f"KRW-{b['currency']}")
                if price:
                    total += (float(b['balance']) + float(b['locked'])) * price
        return total
    except: return 0

# 로그인 및 가동 시작
try:
    upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
    msg = "🚀 봇 가동 시작!\n- 하락장 필터 작동\n- RSI 35/볼밴 진입\n- 9시 보고서 활성"
    logging.info(msg)
    send_telegram(msg)
except Exception as e:
    logging.error(f"로그인 실패: {e}")
    exit()

# 상태 초기화
states = {}
for ticker in TICKERS:
    coin = get_balance_info(ticker)
    states[ticker] = {'step': 1 if coin['balance'] > 0 else 0}

while True:
    try:
        now = datetime.datetime.now()
        
        # [보고서] 매일 아침 9시 자산 현황 보고
        if now.hour == 9 and now.minute == 0 and last_report_date != now.date():
            equity = get_total_equity()
            send_telegram(f"📅 일일 자산 요약\n현재 총 자산: {equity:,.0f} KRW")
            last_report_date = now.date()

        for ticker in TICKERS:
            info = get_indicators(ticker)
            if not info: continue
            
            curr_price = info['current_price']
            coin = get_balance_info(ticker)
            state = states[ticker]
            
            if coin['balance'] > 0:
                profit_rate = (curr_price / coin['avg_buy_price'] - 1) * 100
            else:
                state['step'] = 0
                profit_rate = 0

            # [1] 1차 매수 진입 (추세 확인 + 과매도)
            if state['step'] == 0:
                # RSI 35 이하이거나 볼밴 하단 터치 시 + 단기 하락세가 멈췄을 때
                if (info['rsi'] <= 35 or curr_price <= info['lower_band_safety']) and not info['is_falling_market']:
                    krw = upbit.get_balance("KRW")
                    if krw > 10000:
                        buy_money = krw * 0.2 # 1차 비중 20%
                        upbit.buy_market_order(ticker, buy_money * 0.9995)
                        state['step'] = 1
                        send_telegram(f"🟢 [{ticker}] 진입\n가격: {curr_price:,}원\n목표익절: {info['dynamic_target']:.1f}%")
                        time.sleep(2)

            # [2] 2차 매수 (추매/DCA)
            elif state['step'] == 1:
                # 평단가 대비 3% 이상 하락 & RSI 40 이하로 다시 눌렸을 때
                if curr_price <= coin['avg_buy_price'] * 0.97 and info['rsi'] <= 40:
                    krw = upbit.get_balance("KRW")
                    if krw > 10000:
                        buy_money = (coin['balance'] * coin['avg_buy_price']) * 1.0 # 1차만큼 더 삼
                        upbit.buy_market_order(ticker, min(buy_money, krw * 0.95))
                        state['step'] = 2
                        send_telegram(f"🟡 [{ticker}] 전략적 추매\n수익률: {profit_rate:.2f}%\n평단가 관리 완료")
                        time.sleep(2)

            # [3] 매도 (익절/손절)
            if coin['balance'] > 0:
                # 익절: 동적 목표 달성 시
                if profit_rate >= info['dynamic_target']:
                    upbit.sell_market_order(ticker, coin['balance'])
                    state['step'] = 0
                    send_telegram(f"🔵 [{ticker}] 익절 완료!\n수익: +{profit_rate:.2f}% ✨")
                
                # 손절: 2차 매수 후에도 평단가 대비 5% 하락 시 (최후의 보루)
                elif state['step'] == 2 and profit_rate <= -5.0:
                    upbit.sell_market_order(ticker, coin['balance'])
                    state['step'] = 0
                    send_telegram(f"🔴 [{ticker}] 손절 완료 (원금보호)\n손실: {profit_rate:.2f}% 🚨")

            time.sleep(0.5)
        time.sleep(1)
        
    except Exception as e:
        logging.error(f"메인 루프 에러: {e}")
        time.sleep(10)