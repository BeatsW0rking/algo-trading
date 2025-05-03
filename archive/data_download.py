import backtrader as bt
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import json
import datetime  # For datetime objects
import mongo_atlas

# https://github.com/happydasch/btoandav20
import btoandav20 as bto
import pytz


class noopStrategy(bt.Strategy):

    params = dict(
        weekdays=[],
        tzData=None
    )

    # TODO: Add Timer to find correct M5 Bar
    # TODO: Place Buy Stop with SL & TP
    # TODO: Place Sell Stop with SL & TP

    def log(self, txt=None, dt=None, doprint=False, headers=False):
        ''' Logging function for this strategy'''
        timezone = self.p.tzData

        if headers:
            # naive = datetime.datetime.now()
            # aware1 = naive.astimezone(timezone)
            # print("No Tzinfo:",naive.tzinfo)
            # print("Tzinfo:",aware1)
            # print()
            print('DateTime, Open, High, Low, Close, Volume, Date, DayOfWeek, DayOfMonth, DayOfYear, WeekOfYear, MonthOfYear')
        elif doprint:
            bar = self.datas[0]
            open = format(self.datas[0].open[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
            high = format(self.datas[0].high[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
            low = format(self.datas[0].low[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
            close = format(self.datas[0].close[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
            volume = self.datas[0].volume[0]

            dt = bar.datetime.datetime(0).astimezone(timezone)
            # dt = bar.datetime.datetime(0) #timezone.localize(bar.datetime.datetime(0))
            dtString = dt #.isoformat() 

            print('%s,%s,%s,%s,%s,%s,%s,%d,%d,%d,%d,%d' % (dtString, open, high, low, close, volume,
                bar.datetime.date(0).isoformat(), bar.datetime.date(0).isoweekday(), 
                bar.datetime.date(0).day, bar.datetime.date(0).timetuple().tm_yday,
                bar.datetime.date(0).isocalendar().week, bar.datetime.date(0).month))
            
            
    


    def __init__(self):
        self.orefs = list()
        self.log(headers=True)
        

    def next(self):
        # Simply log the closing price of the series from the reference
        # logmsg = format(
        #         self.datas[0].close[0],
        #         '.%df' % self.datas[0].contractdetails['displayPrecision'])
        self.log(doprint=True)

class mongoStrategy(bt.Strategy):

    OHLCRepo = None
    bars = None

    params = dict(
        weekdays=[],
        tzData=None,
        instrument="",
        timeframe=""
    )


    def log(self):
        ''' Logging function for this strategy'''
        timezone = self.p.tzData
        # print('log called')

        bt_bar = self.datas[0]
        open = format(self.datas[0].open[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
        high = format(self.datas[0].high[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
        low = format(self.datas[0].low[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
        close = format(self.datas[0].close[0],'.%df' % self.datas[0].contractdetails['displayPrecision'])
        volume = self.datas[0].volume[0]

        dt = bt_bar.datetime.datetime(0).astimezone(timezone)
        dtString = dt

        bar = {"open": open,
               "high": high,
               "low": low,
               "close": close,
               "timestamp": dtString}
        
        self.bars.append(bar)
        if len(self.bars)  == 200:
            self.OHLCRepo.insertOHLCs(self.bars)
            self.bars.clear()
         
            
            
    


    def __init__(self):
        # self.orefs = list()
        self.bars = []
        self.OHLCRepo = mongo_atlas.OHLCMongo(self.p.instrument, self.p.timeframe)
        self.OHLCRepo.connect()
        # self.log(headers=True)
        

    def next(self):
        # Simply log the closing price of the series from the reference
        # logmsg = format(
        #         self.datas[0].close[0],
        #         '.%df' % self.datas[0].contractdetails['displayPrecision'])
        self.log()


with open("./secret/config-practice.json", "r") as file:
    config = json.load(file)

storekwargs = dict(
    token=config["oanda"]["token"],
    account=config["oanda"]["account"],
    practice=config["oanda"]["practice"],
    notif_transactions=True,
    stream_timeout=10,
)

# tzData=pytz.timezone('Europe/London')#'Europe/London') #'US/Eastern') 
# fromdate = tzData.localize(datetime.datetime(2023, 6, 4))
# todate = tzData.localize(datetime.datetime(2023, 6, 6))

fromdate = datetime.datetime(2017, 1, 1)
todate = datetime.datetime(2023, 11, 12)

datakwargs = dict(
    historical=True,
    fromdate=fromdate,
    todate=todate,
    timeframe=bt.TimeFrame.Seconds,
    compression=5,
    bidask=False, #Use Mid Price
    tz='Europe/London', #'US/Eastern', 'Europe/Berlin'
)



store = bto.stores.OandaV20Store(**storekwargs)
data = bto.feeds.OandaV20Data(dataname="EUR_USD", **datakwargs)

stratkwargs = dict(
    weekdays=[0,1,2,3,4,5],
    tzData=pytz.timezone('US/Eastern'), 
    instrument="EURUSD",
    timeframe="S5"
)

cerebro = bt.Cerebro()

# Add a writer to get output
# cerebro.addwriter(bt.WriterFile, csv='strategy_false, store_false, broker_false, observer_false', rounding=4) #csv='store_true'
# cerebro.replaydata(data,
#                        timeframe=bt.TimeFrame.Minutes,
#                        compression=5)

# data.resample(
#     timeframe=bt.TimeFrame.Minutes,
#     compression=5)

# data0 = bt.feeds.BacktraderCSVData(dataname='../backtrader/datas/2005-2006-day-001.txt')
cerebro.adddata(data)
# cerebro.addstrategy(noopStrategy, **stratkwargs)
cerebro.addstrategy(mongoStrategy, **stratkwargs)

# Run over everything
strats = cerebro.run()
strat0 = strats[0]

# Print out the final result
# print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

# cerebro.plot()


