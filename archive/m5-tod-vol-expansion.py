import backtrader as bt
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import json
import datetime  # For datetime objects

# https://github.com/happydasch/btoandav20
import btoandav20 as bto


class OrderObserver(bt.observer.Observer):
    lines = ('created', 'expired',)

    plotinfo = dict(plot=True, subplot=True, plotlinelabels=True)

    plotlines = dict(
        created=dict(marker='*', markersize=8.0, color='lime', fillstyle='full'),
        expired=dict(marker='s', markersize=8.0, color='red', fillstyle='full')
    )

    def next(self):
        for order in self._owner._orderspending:
            if order.data is not self.data:
                continue

            # if not order.isbuy():
            #     continue

            if order.status in [bt.Order.Accepted, bt.Order.Submitted]:
                self.lines.created[0] = order.created.price

            elif order.status in [bt.Order.Expired]:
                self.lines.expired[0] = order.created.price

class m5VolExpansion(bt.Strategy):

    params = dict(
        tpRR=2,
        valid_min= 60,
        printlog= True,
        when=bt.timer.SESSION_START,
        timer=True,
        cheat=False,
        tzdata=None,
        offset=datetime.timedelta(),
        repeat=datetime.timedelta(),
        weekdays=[],
    )

    # TODO: Add Timer to find correct M5 Bar
    # TODO: Place Buy Stop with SL & TP
    # TODO: Place Sell Stop with SL & TP

    
    def log(self, txt, dt=None, doprint=False):
        ''' Logging function for this strategy'''
        if self.params.printlog or doprint:
            dt = dt or self.data.datetime.datetime(0) #.date(0) #datetime.datetime(2023, 5, 1) #
            
            print('%s, %s' % (dt, txt))
    
    def __init__(self):
        self.orefs = list()
        self.order_buy = None
        self.order_sell = None
        if self.p.timer:
            self.add_timer(
                when=self.p.when,
                offset=self.p.offset,
                repeat=self.p.repeat,
                weekdays=self.p.weekdays,
                tzdata=self.p.tzdata,
                cheat=self.p.cheat
            )

#     def notify_store(self, msg, *args, **kwargs):
#         self.log('store: %s' % (msg))

    def notify_timer(self, timer, when, *args, **kwargs):
        print('strategy notify_timer with tid {}, when {} cheat {}'.
              format(timer.p.tid, when, timer.p.cheat))

        # if self.order_buy is None:
            
        order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min)
        child_order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min*6)
        price_high = self.data0.high[-1] + 2
        price_low = self.data0.low[-1] - 2
        risk_pips = price_high - price_low

        print('-- {} Order Candle Info: O: {}, H: {}, L {}, C {}, bracket_high: {}, bracket_low: {}'.format(
        self.data.datetime.datetime(), self.data0.open[-1], self.data0.high[-1], self.data0.low[-1], self.data0.close[-1], price_high, price_low ))

        print('-- {} Workout Order size for buy bracket order'.format(
        self.data.datetime.datetime()))
        size = self.getsizer().getsizing(self.data0, isbuy=True, pips=risk_pips, price=price_high, exchange_rate=None)
        # size = 0.1
        print('size:{}',size)
        
        print('-- {} Create buy bracket order'.format(
            self.data.datetime.datetime()))
        
        ob = self.buy_bracket(exectype=bt.Order.Stop,
                                                size=size,
                                                price=price_high,
                                                stopprice=price_low, stopargs=dict(valid=child_order_valid),
                                                limitprice=price_high + ((price_high-price_low) * self.p.tpRR), limitargs=dict(valid=child_order_valid),
                                                valid=order_valid)
        self.orefs.append(o.ref for o in ob)
        
        print('-- {} Workout Order size for sell bracket order'.format(
        self.data.datetime.datetime()))
        # size = self.getsizer().getsizing(self.data0, isbuy=False, pips=risk_pips, price=price_low, exchange_rate=None)
        print('-- {} Create sell bracket order'.format(
            self.data.datetime.datetime()))
        
        os = self.sell_bracket(exectype=bt.Order.Stop,
                                                size=size,
                                                price=price_low,
                                                stopprice=price_high, stopargs=dict(valid=child_order_valid),
                                                limitprice=price_low - ((price_high-price_low) * self.p.tpRR), limitargs=dict(valid=child_order_valid),
                                                valid=order_valid)
        self.orefs.append(o.ref for o in os)

    def notify_order(self, order):
        print('{}: Order ref: {} / Type {} / Status {}'.format(
            self.data.datetime.datetime(0),
            order.ref, 'Buy' * order.isbuy() or 'Sell',
            order.getstatusname()))

        if order.status == order.Completed:
            self.holdstart = len(self)

        if not order.alive() and order.ref in self.orefs:
            self.orefs.remove(order.ref)

    def notify_trade(self, trade):
        if trade.justopened:
            self.log('Trade Opened')
        
        if not trade.isclosed:
            return

        # self.order = None
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))
        
    # def next(self):
        # Simply log the closing price of the series from the reference
        # logmsg = format(
        #         self.datas[0].close[0],
        #         '.%df' % self.datas[0].contractdetails['displayPrecision'])
        # self.log('Close, %s' % logmsg)
        
        
       
    def stop(self):
        self.log('(TP R:R %2d) Ending Value %.2f' %
                 (self.params.tpRR, self.broker.getvalue()), doprint=True)

with open("../secret/config-practice.json", "r") as file:
    config = json.load(file)

storekwargs = dict(
    token=config["oanda"]["token"],
    account=config["oanda"]["account"],
    practice=config["oanda"]["practice"],
    notif_transactions=True,
    stream_timeout=10,
)

datakwargs = dict(
    historical=True,
    fromdate=datetime.datetime(2023, 1, 1),
    todate=datetime.datetime(2023, 5, 16),

    timeframe=bt.TimeFrame.Seconds,
    compression=5,
    tz='Europe/Berlin', #'US/Eastern', #
    backfill=False
    # backfill_start=False
)



store = bto.stores.OandaV20Store(**storekwargs)
# data = store.getdata(dataname="DE30_EUR", **datakwargs)
data = bto.feeds.OandaV20Data(dataname="DE30_EUR", **datakwargs)
  # rightedge=True, boundoff=1)

stratkwargs = dict(
    tpRR=1,
    valid_min= 60,
    #when=bt.timer.SESSION_START,
    when=datetime.time(9, 20),
    tzdata=data,
    timer=True,
    cheat=False,
    # offset=datetime.timedelta(minutes=560),
    repeat=datetime.timedelta(),
    weekdays=[1,2,3,4,5],
)

cerebro = bt.Cerebro()#(stdstats=False)
cerebro.addobserver(bt.observers.DrawDown)
cerebro.addobserver(OrderObserver)
cerebro.addobserver(bt.observers.Trades)
# Add a writer to get output
# cerebro.addwriter(bt.WriterFile, csv=True, rounding=4) #csv='store_true'
cerebro.replaydata(data,
                       timeframe=bt.TimeFrame.Minutes,
                       compression=5)
# data.resample(
#     timeframe=bt.TimeFrame.Minutes,
#     compression=5)
# data0 = bt.feeds.BacktraderCSVData(dataname='../backtrader/datas/2005-2006-day-001.txt')
cerebro.addsizer(bto.sizers.OandaV20BacktestRiskPercentSizer, percents=1)
cerebro.adddata(data)
# cerebro.setbroker(store.getbroker())
# cerebro.broker = bt.brokers.BackBroker()
ci = bto.commissions.OandaV20BacktestCommInfo(pip_location=0)
cerebro.broker.addcommissioninfo(ci)
cerebro.addstrategy(m5VolExpansion, **stratkwargs)

cerebro.addanalyzer(bt.analyzers.PyFolio)

# Print out the starting conditions
# print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

# Run over everything
strats = cerebro.run()
strat0 = strats[0]

# pyfolio = strats.analyzers.getbyname('pyfolio')

# Print out the final result
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

cerebro.plot()

