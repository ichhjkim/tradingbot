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
TICKERS = ["KRW-ETH", "KRW-SOL", "KRW-DOGE"]
SURVIVOR_GOAL = 0.012       # 하락/횡보장 최소 목표 (+1.2%)
BULL_GOAL = 0.025          # 상승장 최소 목표 (+2.5%)
STRICT_SL = -0.05          # 개별 종목 절대 손절선 (-5%)

def send_telegram(message):
    logging.info(f"[Telegram] {message}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 [Survival-V4.2]\n{message}"}
    try:
        requests.get(url, params=params, timeout=5)
    except:
        pass

def get_market_state():
    """상승장인지 하락/횡보장인지 판단 (BTC 기준, 최근 6시간 추세 실시간 반영)"""
    try:
        # 1시간봉 기준 최근 6시간 평균선보다 위에 있는지 확인 (안정성과 반응성의 절충안)
        df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=6)
        ma6 = df['close'].rolling(window=6).mean().iloc[-1]
        curr_p = pyupbit.get_current_price("KRW-BTC")
        return "BULL" if curr_p > ma6 else "BEAR"
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
    daily_profits_done = set()  # 당일 익절 완료된 종목 추적
    FEE = 0.0011               # 업비트 수수료 (매수/매도 합산 + 여유치)
    
    # 가동 시 시장 모드 판단
    m_state = get_market_state()
    current_target = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
    current_indiv_tp = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL # 개별 익절가도 시장에 맞춤

    send_telegram(f"🔥 생존 프로토콜 V4.2 가동\n- 현재 시장: {m_state} 모드\n- 목표 수익률: {current_target*100:.1f}%\n- 종목별 손절선: {STRICT_SL*100}%")

    # 가동 시 잔고 정보 로드 (상태 출항용)
    balances = upbit.get_balances() 
    initial_coin_bals = {f"KRW-{b['currency']}": float(b['balance']) + float(b['locked']) for b in balances if b['currency'] != "KRW"}
    initial_avg_buy_prices = {f"KRW-{b['currency']}": float(b['avg_buy_price']) for b in balances if b['currency'] != "KRW"}

    # 가동 시 이미 보유 중인 코인이 있다면 기준가 출력
    for t, amt in initial_coin_bals.items():
        if t in TICKERS and amt > 1e-8:
            avg_p = initial_avg_buy_prices.get(t, 0)
            if avg_p > 0:
                target_p = avg_p * (1 + current_indiv_tp + FEE)
                stop_p = avg_p * (1 + STRICT_SL + FEE)
                send_telegram(f"🔍 [보유 확인] {t}\n- 평단가: {avg_p:,}원\n- 익절가: {target_p:,.0f}원 (+{current_indiv_tp*100:.1f}%)\n- 손절가: {stop_p:,.0f}원 ({STRICT_SL*100:.1f}%)")

    while True:
        try:
            now = datetime.datetime.now()
            # 업비트 실시간 잔고 및 평단가 정보 한 번에 가져오기
            balances = upbit.get_balances() 
            coin_bals = {f"KRW-{b['currency']}": float(b['balance']) + float(b['locked']) for b in balances if b['currency'] != "KRW"}
            avg_buy_prices = {f"KRW-{b['currency']}": float(b['avg_buy_price']) for b in balances if b['currency'] != "KRW"}
            
            # 9시 리셋 및 생존 판정
            if now.hour == 9 and now.minute == 0 and now.second < 10 and last_reset_date != now.date():
                current_wealth = get_total_wealth(upbit)
                final_profit_rate = (current_wealth / base_asset) - 1 if base_asset > 0 else 0
                
                # [생존 판독] 하루 1.2% 수익 못 내면 시스템 종료 경고
                if final_profit_rate < 0.012:
                    send_telegram(f"⚠️ [생존 실패] 일일 수익률 {final_profit_rate*100:.2f}%로 목표(1.2%) 미달.\n약속대로 시스템을 종료(삭제) 대기 모드로 전환합니다. 💀")
                
                for t, amt in coin_bals.items():
                    if t in TICKERS:
                        avg_p = avg_buy_prices.get(t, 0)
                        if avg_p > 0:
                            curr_p = pyupbit.get_current_price(t)
                            p_rate = (curr_p / avg_p) - 1 - FEE
                            if p_rate >= 0 or p_rate <= STRICT_SL:
                                upbit.sell_market_order(t, amt)
                                send_telegram(f"🌅 9시 장정리 매도: {t}\n수익률: {p_rate*100:.2f}%")
                            else:
                                target_p = avg_p * (1 + current_indiv_tp + FEE)
                                stop_p = avg_p * (1 + STRICT_SL + FEE)
                                send_telegram(f"🌅 9시 전략적 보유: {t}\n- 현재 수익률: {p_rate*100:.2f}%\n- 다음 목표가: {target_p:,.0f}원\n- 다음 손절가: {stop_p:,.0f}원")
                        else:
                            upbit.sell_market_order(t, amt)

                time.sleep(5)
                base_asset = get_total_wealth(upbit)
                target_achieved = False
                daily_profits_done = set() # 일일 종목별 익절 기록 초기화
                last_reset_date = now.date()
                m_state = get_market_state()
                current_target = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
                current_indiv_tp = BULL_GOAL if m_state == "BULL" else SURVIVOR_GOAL
                send_telegram(f"📅 새 날 시작\n- 목표치: {current_target*100:.1f}% ({m_state}장)\n- 자산 기준: {base_asset:,.0f}원")

            current_wealth = get_total_wealth(upbit)
            profit_rate = (current_wealth / base_asset) - 1 if base_asset > 0 else 0
            
            # [조건 충족 시 즉시 종료 - 익절]
            if profit_rate >= current_target and not target_achieved:
                target_achieved = True
                for t, amt in coin_bals.items():
                    if t in TICKERS: upbit.sell_market_order(t, amt)
                send_telegram(f"✅ {m_state} 목표 달성! ({profit_rate*100:.2f}%)\n현 자산: {current_wealth:,.0f}원\n내일까지 휴식합니다.")

            if not target_achieved:
                krw_bal = upbit.get_balance("KRW")
                
                for ticker in TICKERS:
                    curr_p = pyupbit.get_current_price(ticker)
                    if not curr_p: continue
                    
                    # 매수: RSI 30 이하 과매도 구간 사냥 (오늘 익절하지 않은 종목만)
                    if (ticker not in coin_bals or coin_bals[ticker] < 1e-8) and ticker not in daily_profits_done:
                        rsi, l_band = get_indicators(ticker)
                        if rsi is not None and (rsi <= 30 or curr_p <= l_band):
                            if krw_bal > 5000:
                                upbit.buy_market_order(ticker, krw_bal * 0.2)
                                time.sleep(1) # 체결 대기
                                # 새로 산 코인의 평단가 확인
                                new_bal = upbit.get_balances()
                                avg_p = next((float(b['avg_buy_price']) for b in new_bal if f"KRW-{b['currency']}" == ticker), 0)
                                if avg_p > 0:
                                    target_p = avg_p * (1 + current_indiv_tp + FEE)
                                    stop_p = avg_p * (1 + STRICT_SL + FEE)
                                    send_telegram(f"🎣 [{ticker}] 매수 완료\n- 매수가: {avg_p:,}원 (RSI:{rsi:.1f})\n- 익절 목표: {target_p:,.0f}원\n- 손절 기준: {stop_p:,.0f}원")
                                krw_bal = upbit.get_balance("KRW")
                    
                    # 매도: 실시간 업비트 평단가 기반 익절/손절
                    elif ticker in coin_bals and coin_bals[ticker] > 1e-8:
                        avg_buy_price = avg_buy_prices.get(ticker, 0)
                        if avg_buy_price == 0: continue # 평단가 정보를 가져올 수 없는 경우 무시
                        
                        p_rate = (curr_p / avg_buy_price) - 1
                        
                        # 실제 수익은 수수료를 제외해야 함
                        actual_p_rate = p_rate - FEE
                        
                        if actual_p_rate >= current_indiv_tp:
                            upbit.sell_market_order(ticker, coin_bals[ticker])
                            send_telegram(f"💰 [{ticker}] 익절 완료\n- 평단가: {avg_buy_price:,}원\n- 매도가: {curr_p:,}원\n- 세후 수익률: +{actual_p_rate*100:.2f}%")
                            daily_profits_done.add(ticker)
                        elif actual_p_rate <= STRICT_SL:
                            upbit.sell_market_order(ticker, coin_bals[ticker])
                            send_telegram(f"💀 [{ticker}] 방어적 손절\n- 평단가: {avg_buy_price:,}원\n- 매도가: {curr_p:,}원\n- 세후 수익률: {actual_p_rate*100:.2f}%")
                            
                time.sleep(1)
            else:
                time.sleep(60)

        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()