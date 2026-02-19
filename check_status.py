import pyupbit
import pandas as pd

TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE"]
K_VALUE = 0.5

print(f"{'Ticker':<12} | {'Current':<12} | {'Target':<12} | {'MA5':<12} | {'Status'}")
print("-" * 70)

for ticker in TICKERS:
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=6)
        curr_price = pyupbit.get_current_price(ticker)
        
        yesterday = df.iloc[-2]
        today_open = df.iloc[-1]['open']
        target = today_open + (yesterday['high'] - yesterday['low']) * K_VALUE
        ma5 = df['close'].rolling(window=5).mean().iloc[-2]
        
        status = "Needs Breakout"
        if curr_price > target and curr_price > ma5:
            status = "READY TO BUY"
        elif curr_price <= ma5:
            status = "Below MA5 (Downtrend)"
            
        print(f"{ticker:<12} | {curr_price:>12,.0f} | {target:>12,.0f} | {ma5:>12,.0f} | {status}")
    except Exception as e:
        print(f"{ticker:<12} | Error: {e}")
