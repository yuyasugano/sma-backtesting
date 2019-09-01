#!/usr/bin/python
import csv
import time
import json
import talib
import requests
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from backtesting import Backtest
from backtesting import Strategy
from backtesting.lib import crossover

headers = {'Content-Type': 'application/json'}
api_url_base = 'https://public.bitbank.cc'
pair = 'btc_jpy'
period = '5min'

today = datetime.today()
yesterday = today - timedelta(days=1)
today = "{0:%Y%m%d}".format(today)
yesterday = "{0:%Y%m%d}".format(yesterday)

def api_ohlcv(timestamp):
    api_url = '{0}/{1}/candlestick/{2}/{3}'.format(api_url_base, pair, period, timestamp)
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        ohlcv = json.loads(response.content.decode('utf-8'))['data']['candlestick'][0]['ohlcv']
        return ohlcv
    else:
        return None

def SMA(df):
    df1 = df.copy()
    df1["ma25"] = df1.close.rolling(window=25).mean()
    df1["ma75"] = df1.close.rolling(window=75).mean()
    df1["diff"] = df1.ma25 - df1.ma75
    df1["unixtime"] = [datetime.timestamp(t) for t in df.index]

    # line and Moving Average
    xdate = [x.date() for x in df1.index]
    plt.figure(figsize=(15,5))
    plt.plot(xdate, df1.close,label="original")
    plt.plot(xdate, df1.ma75,label="75days")
    plt.plot(xdate, df1.ma25,label="25days")
    plt.xlim(xdate[0], xdate[-1])
    plt.grid()

    # Cross points
    for i in range(1, len(df1)):
        if df1.iloc[i-1]["diff"] < 0 and df1.iloc[i]["diff"] > 0:
            print("{}:GOLDEN CROSS".format(xdate[i]))
            plt.scatter(xdate[i], df1.iloc[i]["ma25"], marker="o", s=100, color="b")
            plt.scatter(xdate[i], df1.iloc[i]["close"], marker="o", s=50, color="b", alpha=0.5)

        if df1.iloc[i-1]["diff"] > 0 and df1.iloc[i]["diff"] < 0:
            print("{}:DEAD CROSS".format(xdate[i]))
            plt.scatter(xdate[i], df1.iloc[i]["ma25"], marker="o", s=100, color="r")
            plt.scatter(xdate[i], df1.iloc[i]["close"], marker="o", s=50, color="r", alpha=0.5)
    plt.legend()

def SMA_TaLib(df):
    df1 = df.copy()
    df1["ma5"] = talib.SMA(df1['close'], timeperiod=5)
    df1["ma15"] = talib.SMA(df1['close'], timeperiod=15)
    df1["diff"] = df1.ma5 - df1.ma15
    df1["unixtime"] = [datetime.timestamp(t) for t in df1.index]

    # line and Moving Average
    fig = plt.figure(figsize=(15,5))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title('btc/jpy by bitbank.cc API')
    ax.plot(df1.index, df1.close,label="original")
    ax.plot(df1.index, df1.ma15,label="15minutes")
    ax.plot(df1.index, df1.ma5,label="5minutes")
    ax.set_xlim(df1.index[0], df1.index[-1])
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(locator))
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    ax.grid()

    # Cross points
    for i in range(1, len(df1)):
        if df1.iloc[i-1]["diff"] < 0 and df1.iloc[i]["diff"] > 0:
            print("{}:GOLDEN CROSS".format(df1.index[i]))
            ax.scatter(df1.index[i], df1.iloc[i]["ma5"], marker="o", s=100, color="b")
            ax.scatter(df1.index[i], df1.iloc[i]["close"], marker="o", s=50, color="b", alpha=0.5)

        if df1.iloc[i-1]["diff"] > 0 and df1.iloc[i]["diff"] < 0:
            print("{}:DEAD CROSS".format(df1.index[i]))
            ax.scatter(df1.index[i], df1.iloc[i]["ma5"], marker="o", s=100, color="r")
            ax.scatter(df1.index[i], df1.iloc[i]["close"], marker="o", s=50, color="r", alpha=0.5)
    ax.legend()

def SMA_Backtesting(values, n):
    """
    Return simple moving average of `values`, at
    each step taking into account `n` previous values.
    """
    close = pd.Series(values)
    return talib.SMA(close, timeperiod=n)

class SmaCross(Strategy):
    
    # Define the two MA lags as *class variables*
    # for later optimization
    n1 = 5
    n2 = 15
    
    def init(self):
        # Precompute two moving averages
        self.sma1 = self.I(SMA_Backtesting, self.data['Close'], self.n1)
        self.sma2 = self.I(SMA_Backtesting, self.data['Close'], self.n2)
    
    def next(self):
        # If sma1 crosses above sma2, buy the asset
        if crossover(self.sma1, self.sma2):
            self.buy()

        # Else, if sma1 crosses below sma2, sell it
        elif crossover(self.sma2, self.sma1):
            self.sell()

def main():
    ohlcv = api_ohlcv(yesterday)
    open, high, low, close, volume, timestamp = [],[],[],[],[],[]

    for i in ohlcv:
        open.append(int(i[0]))
        high.append(int(i[1]))
        low.append(int(i[2]))
        close.append(int(i[3]))
        volume.append(float(i[4]))
        time_str = str(i[5])
        timestamp.append(datetime.fromtimestamp(int(time_str[:10])).strftime('%Y/%m/%d %H:%M:%M'))

    date_time_index = pd.to_datetime(timestamp) # convert to DateTimeIndex type
    df = pd.DataFrame({'open': open, 'high': high, 'low': low, 'close': close}, index=date_time_index)
    # adjustment for JST if required
    # df.index += pd.offsets.Hour(9)

    df_ = df.copy()
    df_.columns = ['Close','Open','High','Low']
    print('{0}\n{1}'.format(yesterday ,df_.head(5)))
    bt = Backtest(df_, SmaCross, cash=1, commission=.002)
    print('Backtesting result:\n', bt.run())

    stats = bt.optimize(n1 = range(5, 15, 5),
                        n2 = range(15, 50, 5),
                        maximize = 'Equity Final [$]',
                        constraint = lambda p: p.n1 < p.n2)
    print('Optimized result:\n', stats)

if __name__ == '__main__':
    main()

