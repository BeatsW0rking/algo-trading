import math
import backtrader as bt
import backtrader.indicators as btind
import datetime 
import csv

class h1OpenAlphaStrategy(bt.Strategy):

    params = dict(
        tzData=None,
        instrument="",
        timeframe="",
        tpRR=2,
        stopLossPadPips=0,
        minRiskPips=5,
        valid_min=50, 
        rangePCEntry=50, # how much of the range retrace before entry triggered.
        when=bt.timer.SESSION_START,
        timer=True,
        cheat=False,
        offset=datetime.timedelta(),
        offsetRangeEnd=datetime.timedelta(),
        repeat=datetime.timedelta(),
        offsetActiveRange=datetime.timedelta(),
        activeRangeRepeat=datetime.timedelta(),
        weekdays=[],
        weekcarry=False,
        monthdays=[],
        monthcarry=True,
        printlog=False,
        logPandL=False,
        stoplossTrail=False,
        stoplossTrailOffset=1,
        businessHours=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
    )

    def log(self, txt, dt=None, doprint=False):
        ''' Logging function for this strategy'''
        if self.params.printlog or doprint:
            dt = dt or self.data.datetime.datetime(0) #.date(0) #datetime.datetime(2023, 5, 1) #
            
            print('%s: %s' % (dt, txt))

    def getHighestPrice(self, intervals=5):
        highest = max(self.data.high.get(size=intervals)) 
        return highest

    def getLowestPrice(self, intervals=5):
        lowest = min(self.data.low.get(size=intervals)) 
        return lowest

    def notify_timer(self, timer, when, *args, **kwargs):

        if timer.p.tid == self.rangeStartTimerId: # Range Start
            # print('strategy notify_timer with tid {}, when {}'.
            #   format(timer.p.tid, when, 'Range Start'))
            # self.close()
            self.rangeStartIndex = len(self)
        if timer.p.tid == self.rangeEndTimerId: # Range End
            self.rangeEndIndex = len(self)
            print('strategy notify_timer with tid {}, when {} {} Start={} End={}'.
              format(timer.p.tid, when, 'Range End', self.rangeStartIndex, self.rangeEndIndex))
            if self.rangeEndIndex - self.rangeStartIndex == 0:
                return
            self.rangeHigh = self.getHighestPrice(self.rangeEndIndex - self.rangeStartIndex) #btind.Highest(self.data.high, period=5).get()[0]#=self.rangeEndIndex - self.rangeStartIndex)
            self.rangeLow = self.getLowestPrice(self.rangeEndIndex - self.rangeStartIndex) #btind.Lowest(self.data.low, period=5).get()[0] #self.rangeEndIndex - self.rangeStartIndex)
            self.rangeActive = True
            self.rangeOrderPlaced = False
            self.tradeDirection = 'bracket'
        if timer.p.tid == self.rangeRepeatTimerId: #and self.rangeActive and len(self.orefs) > 0: # Active Range Repeat Frequency
            print('strategy rangeRepeatTimerId with tid {}, when {} {} Start={} End={} CLOSING TRADES'.
              format(timer.p.tid, when, 'Range End', self.rangeStartIndex, self.rangeEndIndex))
            # print('orefs:{}', self.orefs)
            for oref in self.orefs:
                self.cancel(oref)
            #tmp = self.cancel(oref for oref in self.orefs) # Need to Cancel Orders which means I need to keep Track of the Orders not just the refs
            
            self.close()
            
    def notify_order(self, order):
        self.log('{}: Order ref: {} / Type {} / Status {}'.format(
            self.data.datetime.datetime(0),
            order.ref, 'Buy' * order.isbuy() or 'Sell',
            order.getstatusname()))
        
        if order.status == order.Accepted:
            self.rangeOrderPlaced = True

        if order.status == order.Completed and 'ref' not in self.tradeRecord: #It is the Opening Order
            self.tradeRecord['ref'] = order.ref
            self.tradeRecord['entryPrice'] = order.executed.price
            self.tradeRecord['size'] = order.executed.size
            if order.executed.size > 0:
                self.tradeRecord['direction'] = 'Long'
                self.tradeRecord['slPrice'] = self.tradeRecord['longslPrice']
                self.tradeRecord['tpPrice'] = self.tradeRecord['longtpPrice']
            else:
                self.tradeRecord['direction'] = 'Short'
                self.tradeRecord['slPrice'] = self.tradeRecord['shortslPrice']
                self.tradeRecord['tpPrice'] = self.tradeRecord['shorttpPrice']
    
        elif order.status == order.Completed and 'ref' in self.tradeRecord: #it is the closing Order
            self.tradeRecord['exitPrice'] = order.executed.price

        # print('orefs:{}', self.orefs)
        if not order.alive() and order in self.orefs:
            self.orefs.remove(order)  
    
    def notify_trade(self, trade):
        # if trade.justopened:
        #     self.log('Trade Opened')
        
        if not trade.isclosed:
            return

        if self.p.logPandL:
            self.log('Trade P/L, GROSS %.2f, NET %.2f, Portfolio: Cash %.2f, NAV %.2f' %
                    (trade.pnl, trade.pnlcomm, self.broker.get_cash(), self.broker.get_value()))
            self.logTrade(trade)
            self.tradeRecord = dict()

    def __init__(self):
        self.orefs = list()
        self.firstTime = True
        self.rangeActive = False
        self.rangeStartIndex = None
        self.rangeEndIndex = None
        self.rangeHigh = None
        self.rangeLow = None
        self.entryPriceLevel = None
        self.tradeDirection = None
        self.rangeTradesPlaced = False
        self.tradeRecord = dict()
        if self.p.timer:
            self.rangeStartTimerId = self.add_timer(
                when=self.p.when,
                offset=self.p.offset,
                repeat=self.p.repeat,
                weekdays=self.p.weekdays,
                weekcarry=self.p.weekcarry,
                monthdays=self.p.monthdays,
                monthcarry=self.p.monthcarry,
                cheat= self.p.cheat
                # tzdata=self.p.tzData
            ).p.tid
            self.rangeEndTimerId =self.add_timer(
            when=self.p.when,
            offset=self.p.offsetRangeEnd,
            repeat=self.p.repeat,
            weekdays=self.p.weekdays,
            weekcarry=self.p.weekcarry,
            monthdays=self.p.monthdays,
            monthcarry=self.p.monthcarry,
            cheat= self.p.cheat
            # tzdata=self.p.tzData
            ).p.tid
            self.rangeRepeatTimerId =self.add_timer(
            when=self.p.when,
            offset=self.p.offsetActiveRange,
            repeat=self.p.activeRangeRepeat,
            weekdays=self.p.weekdays,
            weekcarry=self.p.weekcarry,
            monthdays=self.p.monthdays,
            monthcarry=self.p.monthcarry,
            cheat= self.p.cheat
            # tzdata=self.p.tzData
            ).p.tid

    def InBusinessHours(self, time):
        if time.hour in self.p.businessHours:
            return True
        return False

    def evaluateRangeOrderOld(self):
        #TODO: Add flag for implementation of StopTrail in braket orders - stopexec=bt.Order.StopTrail with either amount or percent of price change
        if self.tradeDirection == None:
            return
        
        order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min)
        child_order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min*6)
        
        if not self.InBusinessHours(self.datas[0].datetime.datetime(0)):
            self.tradeDirection = None
            return
            
        # print('-- {} Order Candle Info: O: {}, H: {}, L {}, C {}, bracket_high: {}, bracket_low: {}'.format(
        #     self.data.datetime.datetime(), self.data0.open[-1], self.data0.high[-1], self.data0.low[-1], self.data0.close[-1], entryPrice, entryPrice ))

        if self.tradeDirection == 'long' or self.tradeDirection == 'bracket':
            # Place Buy Limit at top of Range with SL below Range and no TP
            entryPrice = self.rangeHigh 
            slPrice = self.rangeLow - self.p.stopLossPadPips
            risk_pips = entryPrice - slPrice
            if risk_pips < self.p.minRiskPips:
                self.tradeDirection = None
                self.log('RH:{}, RL: {}. SKIPPED LONG: entryPrice: {}, SL: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice))
                return
            # print('-- {} Workout Order size for buy limit order. Risk pips:{}'.format(
            # self.data.datetime.datetime(), risk_pips))
            size = self.getsizer().getsizing(self.data0, isbuy=True, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice + (risk_pips * self.p.tpRR)#((entryPrice - self.rangeLow) * self.p.tpRR)
            if self.p.stoplossTrail:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=slPrice, stopargs=dict(trailamount=risk_pips * self.p.stoplossTrailOffset, valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid)
                for o in ob:
                    self.orefs.append(o)
                # self.orefs.append(o for o in ob)
            else:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                    size=size,
                                    price=entryPrice,
                                    stopprice=slPrice, stopargs=dict(valid=child_order_valid),
                                    limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                    valid=order_valid)
                for o in ob:
                    self.orefs.append(o)
                    # self.orefs.append(o for o in ob)
            # self.tradeDirection = None
            self.tradeRecord['longentryPrice'] = entryPrice
            self.tradeRecord['longslPrice'] = slPrice
            self.tradeRecord['longtpPrice'] = tpPrice
            self.log('RH:{}, RL: {}. LONG: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))

        if self.tradeDirection == 'short' or self.tradeDirection == 'bracket':
            # Place Buy Limit for 50% of Range with SL below Range and TP at TPRR multiple of Risk
            entryPrice = self.rangeLow
            slPrice = self.rangeHigh + self.p.stopLossPadPips
            risk_pips =  slPrice - entryPrice
            if risk_pips < self.p.minRiskPips:
                self.tradeDirection = None
                self.log('RH:{}, RL: {}. SKIPPED SHORT: entryPrice: {}, SL: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice))
                return
            # risk_pips =  self.rangeHigh - self.entryPriceLevel
            # print('-- {} Workout Order size for sell limit order'.format(
            # self.data.datetime.datetime()))
            size = self.getsizer().getsizing(self.data0, isbuy=False, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice - (risk_pips * self.p.tpRR)
            if self.p.stoplossTrail:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=slPrice, stopargs=dict(trailamount=risk_pips * self.p.stoplossTrailOffset, valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid,
                                oco=ob[0])
                for o in ob:
                    self.orefs.append(o)
            else:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopprice=slPrice, stopargs=dict(valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid,
                                oco=ob[0])
                for o in ob:
                    self.orefs.append(o)
            # self.tradeDirection = None
            self.tradeRecord['shortentryPrice'] = entryPrice
            self.tradeRecord['shortslPrice'] = slPrice
            self.tradeRecord['shorttpPrice'] = tpPrice
            self.log('RH:{}, RL: {}. SHORT: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))
            
        self.tradeDirection = None

    def evaluateRangeOrder(self):
        #TODO: Add flag for implementation of StopTrail in braket orders - stopexec=bt.Order.StopTrail with either amount or percent of price change
        if self.tradeDirection == None:
            return
        
        order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min)
        child_order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min*6)
        
        if not self.InBusinessHours(self.datas[0].datetime.datetime(0)):
            self.tradeDirection = None
            return
            
        # print('-- {} Order Candle Info: O: {}, H: {}, L {}, C {}, bracket_high: {}, bracket_low: {}'.format(
        #     self.data.datetime.datetime(), self.data0.open[-1], self.data0.high[-1], self.data0.low[-1], self.data0.close[-1], entryPrice, entryPrice ))
        
        if self.tradeDirection == 'short' or self.tradeDirection == 'bracket':
            # Place Buy Limit for 50% of Range with SL below Range and TP at TPRR multiple of Risk
            entryPrice = self.rangeLow
            slPrice = self.rangeHigh + self.p.stopLossPadPips
            risk_pips =  slPrice - entryPrice
            if risk_pips < self.p.minRiskPips:
                self.tradeDirection = None
                self.log('RH:{}, RL: {}. SKIPPED SHORT: entryPrice: {}, SL: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice))
                return
            # risk_pips =  self.rangeHigh - self.entryPriceLevel
            # print('-- {} Workout Order size for sell limit order'.format(
            # self.data.datetime.datetime()))
            size = self.getsizer().getsizing(self.data0, isbuy=False, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice - (risk_pips * self.p.tpRR)
            if self.p.stoplossTrail:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=slPrice, stopargs=dict(trailamount=risk_pips * self.p.stoplossTrailOffset, valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid,
                                )
                for o in ob:
                    self.orefs.append(o)
            else:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopprice=slPrice, stopargs=dict(valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid,
                                )
                for o in ob:
                    self.orefs.append(o)
            # self.tradeDirection = None
            self.tradeRecord['shortentryPrice'] = entryPrice
            self.tradeRecord['shortslPrice'] = slPrice
            self.tradeRecord['shorttpPrice'] = tpPrice
            self.log('RH:{}, RL: {}. SHORT: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))

        if self.tradeDirection == 'long' or self.tradeDirection == 'bracket':
            # Place Buy Limit at top of Range with SL below Range and no TP
            entryPrice = self.rangeHigh
            slPrice = self.rangeLow - self.p.stopLossPadPips
            risk_pips = entryPrice - slPrice
            if risk_pips < self.p.minRiskPips:
                self.tradeDirection = None
                self.log('RH:{}, RL: {}. SKIPPED LONG: entryPrice: {}, SL: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice))
                return
            # print('-- {} Workout Order size for buy limit order. Risk pips:{}'.format(
            # self.data.datetime.datetime(), risk_pips))
            size = self.getsizer().getsizing(self.data0, isbuy=True, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice + (risk_pips * self.p.tpRR)#((entryPrice - self.rangeLow) * self.p.tpRR)
            if self.p.stoplossTrail:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=slPrice, stopargs=dict(trailamount=risk_pips * self.p.stoplossTrailOffset, valid=child_order_valid),
                                limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                valid=order_valid,
                                oco=ob[0])
                for o in ob:
                    self.orefs.append(o)
                # self.orefs.append(o for o in ob)
            else:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                    size=size,
                                    price=entryPrice,
                                    stopprice=slPrice, stopargs=dict(valid=child_order_valid),
                                    limitprice= tpPrice, limitargs=dict(valid=child_order_valid),
                                    valid=order_valid,
                                    oco=ob[0])
                for o in ob:
                    self.orefs.append(o)
                    # self.orefs.append(o for o in ob)
            # self.tradeDirection = None
            self.tradeRecord['longentryPrice'] = entryPrice
            self.tradeRecord['longslPrice'] = slPrice
            self.tradeRecord['longtpPrice'] = tpPrice
            self.log('RH:{}, RL: {}. LONG: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))
            
        self.tradeDirection = None

    def next(self):
        if self.p.printlog and len(self) % 1000 == 0:
            self.log(self.data.close[0])
        
        self.evaluateRangeOrder()
  
    
    def logTrade(self, trade):
        # - ``ref``: unique trade identifier
        # - ``status`` (``int``): one of Created, Open, Closed
        # - ``tradeid``: grouping tradeid passed to orders during creation The default in orders is 0
        # - ``size`` (``int``): current size of the trade
        # - ``price`` (``float``): current price of the trade
        # - ``value`` (``float``): current value of the trade
        # - ``commission`` (``float``): current accumulated commission
        # - ``pnl`` (``float``): current profit and loss of the trade (gross pnl)
        # - ``pnlcomm`` (``float``): current profit and loss of the trade minus commission (net pnl)
        # - ``isclosed`` (``bool``): records if the last update closed (set size to null the trade
        # - ``isopen`` (``bool``): records if any update has opened the trade
        # - ``justopened`` (``bool``): if the trade was just opened
        # - ``baropen`` (``int``): bar in which this trade was opened
        # - ``dtopen`` (``float``): float coded datetime in which the trade was opened - Use method ``open_datetime`` to get a Python datetime.datetime or use the platform provided ``num2date`` method
        # - ``barclose`` (``int``): bar in which this trade was closed
        # - ``dtclose`` (``float``): float coded datetime in which the trade was closed - Use method ``close_datetime`` to get a Python datetime.datetime or use the platform provided ``num2date`` method
        # - ``barlen`` (``int``): number of bars this trade was open
        # - ``historyon`` (``bool``): whether history has to be recorded

        tradeHeaders = [
            'ref',
            'direction',
            'entryPrice',
            'exitPrice',
            'slPrice',
            'tpPrice',
            'size',
            'RR',
            'length',
            'win',
            'pnl',
            'entryTime',
            'exitTime'
        ]
        
        if trade.pnl > 0: 
            win = 1
        else:
            win = -1
   
        if abs(self.tradeRecord['entryPrice'] - self.tradeRecord['slPrice']) == 0:
            RR = 0
        else:
            RR = (self.tradeRecord['exitPrice'] - self.tradeRecord['entryPrice']) / abs(self.tradeRecord['entryPrice'] - self.tradeRecord['slPrice'])
        self.tradeRecord['RR'] = RR
        self.tradeRecord['length'] = (trade.close_datetime(tz=self.p.tzData) - trade.open_datetime(tz=self.p.tzData)).total_seconds()
        self.tradeRecord['win'] = win
        self.tradeRecord['pnl'] = trade.pnl
        self.tradeRecord['entryTime'] = trade.open_datetime(tz=self.p.tzData)
        self.tradeRecord['exitTime'] = trade.close_datetime(tz=self.p.tzData)
        
        # self.log(self.tradeRecord)
        # tradeRecord = [trade.ref, trade.size, trade.open_datetime(tz=self.p.tzData), trade.close_datetime(tz=self.p.tzData), trade.pnl, trade.pnlcomm, trade.commission ]

        # del  self.tradeRecord['key']
        
        # with open('trades.csv', 'w', newline='') as csvfile:
        #     tradeRecorder = csv.writer(csvfile, delimiter=',',
        #                     quotechar='|', quoting=csv.QUOTE_MINIMAL)
        #     tradeRecorder.writerow(self.tradeRecord.values())
  
        
        with open('trades.csv', 'a', newline='') as csvfile:
            tradeRecorder = csv.DictWriter(csvfile, fieldnames=tradeHeaders, extrasaction ='ignore', delimiter=',')
            if self.firstTime:
                tradeRecorder.writeheader()
                self.firstTime = False
            tradeRecorder.writerow(self.tradeRecord)

        # self.firstTime = False
        
    #TODO: Take account of Spread on trades to get right R:R