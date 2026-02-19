import time
import pyupbit
import datetime
import pandas as pd
from dotenv import load_dotenv
import os
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading2.log"),
        logging.StreamHandler()
    ]
)

# 환경 변수 로드
load_dotenv()
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")

TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]

def get_rsi(ticker, interval="minute15", count=200):
    """RSI 지표 계산"""
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    delta = df['close'].diff()
    ups, downs = delta.copy(), delta.copy()
    ups[ups < 0] = 0
    downs[downs > 0] = 0

    period = 14
    au = ups.ewm(com=period-1, min_periods=period).mean()
    ad = downs.abs().ewm(com=period-1, min_periods=period).mean()
    rs = au / ad
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_indicators(ticker):
    """볼린저 밴드 지표 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="minute15", count=20)
    ma20 = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    upper_band = ma20 + (std * 2)
    lower_band = ma20 - (std * 2)
    
    return {
        "current_price": df['close'].iloc[-1],
        "lower_band": lower_band.iloc[-1],
        "upper_band": upper_band.iloc[-1]
    }

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            return float(b['balance']) if b['balance'] is not None else 0
    return 0

# 로그인
try:
    upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
    logging.info("Bot2 Started: RSI + Bollinger Band Scalping Strategy")
except Exception as e:
    logging.error(f"Login Failed: {e}")
    exit()

states = {}
for ticker in TICKERS:
    states[ticker] = {
        'holding': False,
        'purchase_price': 0,
        'trade_count_today': 0
    }

current_day = datetime.datetime.now().day

while True:
    try:
        now = datetime.datetime.now()
        
        # 날짜 바뀌면 거래 횟수 리셋
        if now.day != current_day:
            current_day = now.day
            for ticker in TICKERS:
                states[ticker]['trade_count_today'] = 0
            logging.info("New day started. Trade counts reset.")

        for ticker in TICKERS:
            try:
                info = get_indicators(ticker)
                rsi = get_rsi(ticker)
                state = states[ticker]
                
                # 매수 로직: RSI가 35 이하이면서 가격이 볼린저 밴드 하단 근처일 때
                if not state['holding']:
                    if rsi <= 35 and info['current_price'] <= info['lower_band'] * 1.01:
                        krw = get_balance("KRW")
                        buy_amount = krw * 0.3 # 가용 자금의 30% 투자
                        if buy_amount > 5000:
                            logging.info(f"[BUY] {ticker} | Price: {info['current_price']} | RSI: {rsi:.2f}")
                            upbit.buy_market_order(ticker, buy_amount * 0.9995)
                            state['holding'] = True
                            state['purchase_price'] = info['current_price']
                            time.sleep(1)

                # 매도 로직: 익절 1.5% 또는 RSI가 65 이상으로 과열될 때
                elif state['holding']:
                    current_price = info['current_price']
                    profit_rate = (current_price / state['purchase_price'] - 1) * 100
                    
                    # 1. 익절: 1.5% 수익 OR RSI 65 이상
                    if profit_rate >= 1.5 or rsi >= 65:
                        coin_symbol = ticker.split("-")[1]
                        balance = get_balance(coin_symbol)
                        if balance * current_price > 5000:
                            logging.info(f"[SELL-Profit] {ticker} | Rate: {profit_rate:.2f}% | RSI: {rsi:.2f}")
                            upbit.sell_market_order(ticker, balance)
                            state['holding'] = False

                    # 2. 손절: 1.5% 손실 (안전 장치)
                    elif profit_rate <= -1.5:
                        coin_symbol = ticker.split("-")[1]
                        balance = get_balance(coin_symbol)
                        if balance * current_price > 5000:
                            logging.warn(f"[SELL-Loss] {ticker} | Rate: {profit_rate:.2f}%")
                            upbit.sell_market_order(ticker, balance)
                            state['holding'] = False
                
                time.sleep(0.5) # API 호출 제한 방지
            except Exception as e:
                logging.error(f"Error in {ticker}: {e}")
                time.sleep(1)

        time.sleep(1)
    except Exception as e:
        logging.error(f"Main Loop Error: {e}")
        time.sleep(5)
