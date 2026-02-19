import pyupbit
import numpy as np

# OHLCV(open, high, low, close, volume)로 당일 시가, 고가, 저가, 종가, 거래량 데이터 추출
df = pyupbit.get_ohlcv("KRW-BTC", count=30)

# 변동폭 출력 > (고가 - 저가) * k값
df['range'] = (df['high'] - df['low']) * 0.5

# 매수가 변동폭 > 시가 + 변동폭
df['target'] = df['open'] + df['range'].shift(1)

# ror(수익률), np.where(조건문, 참일때 값, 거짓일때 값)
df['ror'] = np.where(df['high'] > df['target'],
                     df['close'] / df['target'],
                     1)

# 누적 수익률(hpr) > ror의 곱
df['hpr'] = df['ror'].cumprod()

# Draw Down 계산 (고점 대비 낙폭)
df['dd'] = (df['hpr'].cummax() - df['hpr']) / df['hpr'].cummax() * 100

# MDD 계산
print("MDD(%): ", df['dd'].max())

# 엑셀 출력
df.to_excel("dd.xlsx")
print("Backtest completed. Check dd.xlsx for results.")
