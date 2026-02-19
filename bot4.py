import time
import pyupbit
import datetime
import os
import logging
import requests
from dotenv import load_dotenv

# [Bot4 - V4.2 Ultimate Survival Edition]
# MISSION: 
# 1. Down/Sideways Market -> Min 0.5% Profit
# 2. Up Market -> Min 1.0% Profit
# 3. ABSOLUTE LIMIT: Max 2% Loss (Strict TP/SL)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot4_trading.log", encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True
)

ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------------------
# 세부 전략 설정 (생존 필수 조건 반영)
# ---------------------------------------------------------------------
TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE"]
SURVIVOR_GOAL = 0.007      # 하락/횡보장 최소 목표 (+0.7%)
BULL_GOAL = 0.015         # 상승장 최소 목표 (+1.5%)
STRICT_SL = -0.037        # 개별 종목 절대 손절선 (사용자 설정 기준)

def send_telegram(message):
    logging.info(f"[Telegram] {message}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 [Survival-V4.2]\n{message}"}
    try:
        requests.get(url, params=params, timeout=5)
    except:
        pass

def get_market_state():
    """상승장인지 하락/횡보장인지 판단 (BTC 기준)"""
    try:
        df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=5)
        ma5 = df['close'].rolling(window=5).mean().iloc[-1]
        curr_p = pyupbit.get_current_price("KRW-BTC")
        return "BULL" if curr_p > ma5 else "BEAR"
    except:
        return "BEAR"

def get_indicators(ticker):
    """15분봉 RSI 및 볼린저 밴드 하단"""
    try:
        df = pyupbit.get_ohlcv(ticker, interval="minute15", count=100)
        delta = df['close'].diff()
        ups, downs = delta.copy(), delta.copy()
        ups[ups < 0], downs[downs > 0] = 0, 0
        au = ups.ewm(com=13, min_periods=14).mean()
        ad = downs.abs().ewm(com=13, min_periods=14).mean()
        rsi = 100 - (100 / (1 + au / ad))
        lower_band = df['close'].rolling(window=20).mean() - (df['close'].rolling(window=20).std() * 2)
        return rsi.iloc[-1], lower_band.iloc[-1]
    except: return None, None

def get_total_wealth(upbit):
    try:
        balances = upbit.get_balances()
        total = 0
        for b in balances:
            price = pyupbit.get_current_price(f"KRW-{b['currency']}") if b['currency'] != "KRW" else 1
            if price: total += (float(b['balance']) + float(b['locked'])) * price
        return total
    except: return 0

def get_coin_balances(upbit):
    try:
        balances = upbit.get_balances()
        return {f"KRW-{b['currency']}": float(b['balance']) + float(b['locked']) for b in balances if b['currency'] != "KRW"}
    except: return {}

# ---------------------------------------------------------------------
# 실행 엔진
# ---------------------------------------------------------------------
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

def run_bot():
    base_asset = get_total_wealth(upbit)
    last_reset_date = datetime.datetime.now().date()
    target_achieved = False
    entry_prices = {}
    daily_profits_done = set()  # 당일 익절 완료된 종목 추적
    
    # 가동 시 시장 모드 판단
    m_state = get_market_state()
    current_target = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
    current_indiv_tp = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL # 개별 익절가도 시장에 맞춤

    send_telegram(f"🔥 생존 프로토콜 V4.2 가동\n- 현재 시장: {m_state} 모드\n- 목표 수익률: {current_target*100:.1f}%\n- 종목별 손절선: {STRICT_SL*100}%")

    while True:
        try:
            now = datetime.datetime.now()
            
            # 9시 리셋
            if now.hour == 9 and now.minute == 0 and now.second < 10 and last_reset_date != now.date():
                coin_bals = get_coin_balances(upbit)
                for t, amt in coin_bals.items():
                    if t in TICKERS: upbit.sell_market_order(t, amt)
                time.sleep(5)
                base_asset = get_total_wealth(upbit)
                target_achieved = False
                daily_profits_done = set() # 일일 종목별 익절 기록 초기화
                last_reset_date = now.date()
                entry_prices = {}
                m_state = get_market_state()
                current_target = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
                current_indiv_tp = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
                send_telegram(f"📅 리셋 완료\n- 목표치 재설정: {current_target*100:.1f}% ({m_state}장)")

            current_wealth = get_total_wealth(upbit)
            profit_rate = (current_wealth / base_asset) - 1 if base_asset > 0 else 0
            
            # [조건 충족 시 즉시 종료 - 익절]
            if profit_rate >= current_target and not target_achieved:
                target_achieved = True
                coin_bals = get_coin_balances(upbit)
                for t, amt in coin_bals.items():
                    if t in TICKERS: upbit.sell_market_order(t, amt)
                send_telegram(f"✅ {m_state} 목표 달성! ({profit_rate*100:.2f}%)\n현 자산: {current_wealth:,.0f}원\n내일까지 휴식합니다.")

            if not target_achieved:
                krw_bal = upbit.get_balance("KRW")
                coin_bals = get_coin_balances(upbit)
                
                for ticker in TICKERS:
                    curr_p = pyupbit.get_current_price(ticker)
                    if not curr_p: continue
                    
                    # 매수: RSI 30 이하 과매도 구간 사냥 (오늘 익절하지 않은 종목만)
                    if (ticker not in coin_bals or coin_bals[ticker] < 1e-8) and ticker not in daily_profits_done:
                        rsi, l_band = get_indicators(ticker)
                        if rsi is not None and (rsi <= 30 or curr_p <= l_band):
                            if krw_bal > 5000:
                                upbit.buy_market_order(ticker, krw_bal * 0.2)
                                entry_prices[ticker] = curr_p
                                send_telegram(f"🎣 [{ticker}] 타점 포착\n가격: {curr_p:,}원 / RSI: {rsi:.1f}")
                                time.sleep(0.5)
                                krw_bal = upbit.get_balance("KRW")
                    
                    # 매도: 개별 TP/SL
                    elif ticker in entry_prices:
                        p_rate = (curr_p / entry_prices[ticker]) - 1
                        if p_rate >= current_indiv_tp:
                            upbit.sell_market_order(ticker, coin_bals[ticker])
                            send_telegram(f"💰 [{ticker}] 익절 완료\n- 매수가: {entry_prices[ticker]:,}원\n- 매도가: {curr_p:,}원\n- 수익률: +{p_rate*100:.2f}%\n- 해당 종목은 내일 9시에 다시 가동합니다.")
                            daily_profits_done.add(ticker) # 금일 해당 종목 매매 종료
                            del entry_prices[ticker]
                        elif p_rate <= STRICT_SL:
                            upbit.sell_market_order(ticker, coin_bals[ticker])
                            send_telegram(f"💀 [{ticker}] 방어적 손절\n- 매수가: {entry_prices[ticker]:,}원\n- 매도가: {curr_p:,}원\n- 수익률: {p_rate*100:.2f}%")
                            del entry_prices[ticker]
                            
                time.sleep(1)
            else:
                time.sleep(60)

        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()