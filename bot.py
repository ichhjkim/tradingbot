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
        logging.FileHandler("trading.log"),
        logging.StreamHandler()
    ]
)

# 환경 변수 로드
load_dotenv()

ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")  

TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
K_VALUE = 0.5

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    if df is not None:
        return df.index[0]
    return None

def get_ma2(ticker):
    """2일 이동 평균선 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    if df is not None:
        ma2 = df['close'].rolling(window=2).mean().iloc[-1]
        return ma2
    return None

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

# 로그인
try:
    upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
    logging.info("Trading Bot Started (BTC, ETH, SOL) - Strategy Update: MA2, TP 1.5%, SL 2.0%")
except Exception as e:
    logging.error(f"Login Failed: {e}")
    exit()

# 코인별 상태 관리를 위한 딕셔너리
states = {}

def update_daily_data():
    """하루에 한 번, 매수 목표가와 이동평균선 등을 갱신"""
    for ticker in TICKERS:
        try:
            time.sleep(0.1) # API 호출 제한 방지
            states[ticker] = {
                'holding': states.get(ticker, {}).get('holding', False), # 기존 보유 상태 유지
                'purchase_price': states.get(ticker, {}).get('purchase_price', 0),
                'trade_completed_today': False, # 날짜 바뀌면 리셋
                'target_price': get_target_price(ticker, K_VALUE),
                'ma2': get_ma2(ticker)
            }
            logging.info(f"Updated daily data for {ticker}: Target={states[ticker]['target_price']}, MA2={states[ticker]['ma2']}")
        except Exception as e:
            logging.error(f"Failed to update daily data for {ticker}: {e}")

# 초기 데이터 설정
current_day = datetime.datetime.now().day
update_daily_data()

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        
        # 날짜가 바뀌면 데이터 갱신 및 플래그 초기화
        if now.day != current_day:
            current_day = now.day
            logging.info("New day started. Updating daily data...")
            update_daily_data()

        # 공통 시작 시간 (API 호출 최소화 위해 대략적인 시간 계산 혹은 1분 1회 체크가 좋으나, 여기선 간단히 BTC 기준으로 캐싱 가능)
        # 하지만 안전을 위해 매번 체크하되, 에러 시 무시
        try:
            # start_time은 잘 안 바뀌므로 BTC 조회 비용 감수 (1초 1회는 허용 범위)
            # 더 최적화하려면 이것도 변수에 저장 가능하나, 업비트 점검 등으로 시간이 밀릴 수 있어 조회 유지
            start_time = get_start_time("KRW-BTC") 
            end_time = start_time + datetime.timedelta(days=1)
        except:
            time.sleep(1)
            continue

        for ticker in TICKERS:
            # 09:00:00 ~ 다음날 08:59:50 (매수/보유 구간)
            if start_time < now < end_time - datetime.timedelta(seconds=10):
                current_price = get_current_price(ticker)
                state = states[ticker]

                # 1. 매매 로직
                if not state['holding'] and not state['trade_completed_today']:
                    # 캐싱된 값 사용 (API 호출 X)
                    target_price = state['target_price']
                    ma2 = state['ma2']
                    
                    # target_price나 ma2가 계산 오류로 None일 수 있음
                    if target_price is not None and ma2 is not None:
                        if target_price < current_price and ma2 < current_price:
                            krw = get_balance("KRW")
                            buy_amount = krw * 0.3
                            if buy_amount > 5000:
                                logging.info(f"Target Met! Buying {ticker}. Price: {current_price}")
                                upbit.buy_market_order(ticker, buy_amount * 0.9995)
                                state['holding'] = True
                                state['purchase_price'] = current_price
                                time.sleep(1)

                # 2. 실시간 감시 (보유 중일 때)
                elif state['holding']:
                    # 익절: 1.5% 수익 (수정됨)
                    if current_price >= state['purchase_price'] * 1.015:
                        coin_symbol = ticker.split("-")[1]
                        balance = get_balance(coin_symbol)
                        
                        # 잔고가 너무 작으면(매도 후 남은 찌꺼기) 무시
                        if balance * current_price > 5000:
                            logging.info(f"Take Profit! {ticker} (1.5% hit). Selling at {current_price}")
                            upbit.sell_market_order(ticker, balance)
                            state['holding'] = False
                            state['trade_completed_today'] = True

                    # 손절: 2% 손실 (수정됨)
                    elif current_price <= state['purchase_price'] * 0.98:
                        coin_symbol = ticker.split("-")[1]
                        balance = get_balance(coin_symbol)
                        
                        if balance * current_price > 5000:
                            logging.warn(f"Stop Loss! {ticker} (2% hit). Selling at {current_price}")
                            upbit.sell_market_order(ticker, balance)
                            state['holding'] = False
                            state['trade_completed_today'] = True
            
            # 마감 전량 매도
            else:
                state = states[ticker]
                if state['holding']:
                    coin_symbol = ticker.split("-")[1]
                    balance = get_balance(coin_symbol)
                    if balance * get_current_price(ticker) > 5000:
                        logging.info(f"End of session. Market exit {ticker}.")
                        upbit.sell_market_order(ticker, balance)
                    state['holding'] = False
                    state['purchase_price'] = 0
            
        time.sleep(1)
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        time.sleep(5)
