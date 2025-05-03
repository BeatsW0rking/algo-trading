import backtrader as bt
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import backtrader.analyzers as btanalyzers

import json
import datetime  # For datetime objects

# https://github.com/happydasch/btoandav20
import btoandav20 as bto
import pytz
import argparse
# import oanda_downloader 
import timedRangeStrategy
import h1OpenAlphaStrategy


def runBackTesterStrategy(strategy, stratargs, instrument, fromdate, todate):
    # print(instrument, fromdate, todate)

    with open("../secret/config-practice.json", "r") as file:
        config = json.load(file)

    storekwargs = dict(
        token=config["oanda"]["token"],
        account=config["oanda"]["account"],
        practice=config["oanda"]["practice"],
        notif_transactions=True,
        stream_timeout=20,
    )

    #'Europe/London') #'US/Eastern') 
    # fromdate2 = tzData.localize(fromdate)
    # todate2 = tzData.localize(todate)

    datakwargs = dict(
        historical=True,
        fromdate=fromdate,
        todate=todate,
        timeframe=bt.TimeFrame.Seconds,
        compression=5,
        bidask=False, #Use Mid Price
        tz='US/Eastern', #'US/Eastern', 'Europe/Berlin',
        sessionstart=datetime.time(2, 0),
        sessionend=datetime.time(15, 45),
    )

    store = bto.stores.OandaV20Store(**storekwargs)
    data = bto.feeds.OandaV20Data(dataname=instrument, **datakwargs)

    stratkwargs = stratargs

    cerebro = bt.Cerebro()
    cerebro.addobserver(bt.observers.DrawDown)
    # cerebro.addobserver(OrderObserver)
    cerebro.addsizer(bto.sizers.OandaV20BacktestRiskSizer, amount=10)#(bto.sizers.OandaV20BacktestRiskPercentSizer, percents=1)
    cerebro.adddata(data)
    ci = bto.commissions.OandaV20BacktestCommInfo(pip_location=0)
    # cerebro.broker = store.getbroker()
    cerebro.broker.addcommissioninfo(ci)
    cerebro.addstrategy(strategy, **stratkwargs)


    # Analyzer
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='mysharpe')
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='mytrades')
    
    # Run over everything
    strats = cerebro.run()

    thestrat = strats[0]

    print('Sharpe Ratio:', thestrat.analyzers.mysharpe.get_analysis())
    print('Trade Analysis:', thestrat.analyzers.mytrades.get_analysis())
    
    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

    cerebro.plot()


def main():
    parser = argparse.ArgumentParser("Strategy runner")
    parser.add_argument("Strategy", help="The Strategy to backtest", type=str)
    parser.add_argument("Instrument", help="The Instrument to backtest", type=str)
    parser.add_argument("FromYear", help="The Year part of the Date to request Instrument Data From", type=int)
    parser.add_argument("FromMonth", help="The Month part of the Date to request Instrument Data From", type=int)
    parser.add_argument("FromDay", help="The Day part of the Date to request Instrument Data From", type=int)
    parser.add_argument("ToYear", help="The Year part of the Date to request Instrument Data To", type=int)
    parser.add_argument("ToMonth", help="The Month part of the Date to request Instrument Data To", type=int)
    parser.add_argument("ToDay", help="The Day part of the Date to request Instrument Data To", type=int)


    args = parser.parse_args()

    instrument = args.Instrument #"EUR_USD"
    fromdate = datetime.datetime(args.FromYear, args.FromMonth, args.FromDay)
    todate = datetime.datetime(args.ToYear, args.ToMonth, args.ToDay)
    
    strategy = ''
    if args.Strategy == "timedRange":
       strategy = timedRangeStrategy.timedRangeStrategy
       tzData = pytz.timezone('US/Eastern')
       stratkwargs = dict(
        tzData=tzData, 
        instrument=instrument,
        timeframe="S5",
        tpRR=5,
        stopLossPadPips=2,
        valid_min= 60,
        rangePCEntry=50,
        when=bt.timer.SESSION_START,
        timer=True,
        cheat=False,
        offsetRangeEnd=datetime.timedelta(minutes=14),
        repeat=datetime.timedelta(),
        activeRangeRepeat=datetime.timedelta(minutes=5),
        weekdays=[],
        weekcarry=False,
        monthdays=[],
        monthcarry=True,
        printlog=True,
        logPandL=True,
        stoplossTrail=True
        )
    elif args.Strategy == 'h1OpenAlpha':
       strategy = h1OpenAlphaStrategy.h1OpenAlphaStrategy
       tzData = pytz.timezone('US/Eastern')
       stratkwargs = dict(
        tzData=tzData, 
        instrument=instrument,
        timeframe="S5",
        tpRR=5,
        stopLossPadPips=4,
        minRiskPips=5,
        valid_min= 10,
        rangePCEntry=50,
        when=bt.timer.SESSION_START,
        timer=True,
        cheat=False,
        offset=datetime.timedelta(minutes=0),
        offsetRangeEnd=datetime.timedelta(minutes=1),
        repeat=datetime.timedelta(minutes=60),
        offsetActiveRange=datetime.timedelta(minutes=58),
        activeRangeRepeat=datetime.timedelta(minutes=60),
        weekdays=[],
        weekcarry=False,
        monthdays=[],
        monthcarry=True,
        printlog=True,
        logPandL=True,
        stoplossTrail=False,
        stoplossTrailOffset=2,
        businessHours=[2,3,4,5,6,7,8,9,10,11,12,13,14,16,17,18,19,20],
        )

    print(datetime.datetime.today().isoformat(" ","seconds"),":", "Executing  with:", instrument, fromdate, todate)


    runBackTesterStrategy(strategy, stratkwargs, instrument, fromdate, todate)


if __name__ == "__main__":
    main()
