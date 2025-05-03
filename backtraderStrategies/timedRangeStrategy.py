import backtrader as bt
import backtrader.indicators as btind
import datetime 

class timedRangeStrategy(bt.Strategy):

    params = dict(
        tzData=None,
        instrument="",
        timeframe="",
        tpRR=2,
        stopLossPadPips=0,
        valid_min=60, 
        rangePCEntry=50, # how much of the range retrace before entry triggered.
        when=bt.timer.SESSION_START,
        timer=True,
        cheat=False,
        offset=datetime.timedelta(),
        offsetRangeEnd=datetime.timedelta(),
        repeat=datetime.timedelta(),
        activeRangeRepeat=datetime.timedelta(),
        weekdays=[],
        weekcarry=False,
        monthdays=[],
        monthcarry=True,
        printlog=False,
        logPandL=False,
        stoplossTrail=False
    )

    def log(self, txt, dt=None, doprint=False):
        ''' Logging function for this strategy'''
        if self.params.printlog or doprint:
            dt = dt or self.data.datetime.datetime(0) #.date(0) #datetime.datetime(2023, 5, 1) #
            
            print('%s: %s' % (dt, txt))

    def getHighestPrice(self, intervals=5):
        highest = max(self.data.high.get(size=intervals)) 
        # highest = 0
        # for i in range(intervals):
        #     highest = max(highest, self.data.high[-i])
        return highest

    def getLowestPrice(self, intervals=5):
        lowest = min(self.data.low.get(size=intervals)) 
        return lowest

    def notify_timer(self, timer, when, *args, **kwargs):

        if timer.p.tid == self.rangeStartTimerId: # Range Start
            # print('strategy notify_timer with tid {}, when {}'.
            #   format(timer.p.tid, when, 'Range Start'))
            self.close()
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
            # print('strategy notify_timer with tid {}, when {} {} Start={}, high={}, rangeHigh={}, rangeLow={}'.
            #   format(timer.p.tid, when, 'Range End', self.rangeStartIndex, self.data.high[0], self.rangeHigh, self.rangeLow))
        if timer.p.tid == self.rangeRepeatTimerId and self.rangeActive and self.rangeOrderPlaced == False: # Active Range Repeat Frequency
            if self.data.close > self.rangeHigh:
                self.tradeDirection = 'long'
                self.entryPriceLevel = self.rangeLow + ((self.rangeHigh - self.rangeLow) * (self.p.rangePCEntry/100))
                # print('strategy notify_timer with tid {}, when {}, {}, entryPriceLevel: {}'.
                #     format(timer.p.tid, when, 'Looking for Longs', self.entryPriceLevel))
            elif self.data0.close < self.rangeLow:
                self.tradeDirection = 'short'
                self.entryPriceLevel = self.rangeHigh - ((self.rangeHigh - self.rangeLow) * (self.p.rangePCEntry/100))
                # print('strategy notify_timer with tid {}, when {}, {}, entryPriceLevel: {}'.
                #     format(timer.p.tid, when, 'Looking for Shorts', self.entryPriceLevel))

    def notify_order(self, order):
        # self.log('{}: Order ref: {} / Type {} / Status {}'.format(
        #     self.data.datetime.datetime(0),
        #     order.ref, 'Buy' * order.isbuy() or 'Sell',
        #     order.getstatusname()))
        
        if order.status == order.Accepted:
            self.rangeOrderPlaced = True

        # if order.status == order.Completed:
        #     self.log('{} Buy Exec @ {}'.format(
        #         self.data.datetime.datetime(), order.executed.price))

        if not order.alive() and order.ref in self.orefs:
            self.orefs.remove(order.ref)  
    
    def notify_trade(self, trade):
        # if trade.justopened:
        #     self.log('Trade Opened')
        
        if not trade.isclosed:
            return

        if self.p.logPandL:
            self.log('Trade P/L, GROSS %.2f, NET %.2f, Portfolio: Cash %.2f, NAV %.2f' %
                    (trade.pnl, trade.pnlcomm, self.broker.get_cash(), self.broker.get_value()))

    def __init__(self):
        self.orefs = list()
        self.rangeActive = False
        self.rangeStartIndex = None
        self.rangeEndIndex = None
        self.rangeHigh = None
        self.rangeLow = None
        self.entryPriceLevel = None
        self.tradeDirection = None
        self.rangeTradesPlaced = False
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
            offset=self.p.offset,
            repeat=self.p.activeRangeRepeat,
            weekdays=self.p.weekdays,
            weekcarry=self.p.weekcarry,
            monthdays=self.p.monthdays,
            monthcarry=self.p.monthcarry,
            cheat= self.p.cheat
            # tzdata=self.p.tzData
            ).p.tid

    def evaluateRangeOrder(self):
        #TODO: Add flag for implementation of StopTrail in braket orders - stopexec=bt.Order.StopTrail with either amount or percent of price change
        if self.tradeDirection == None:
            return
        
        order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min)
        child_order_valid = self.datas[0].datetime.datetime(0) + datetime.timedelta(minutes=self.p.valid_min*6)
        entryPrice = self.entryPriceLevel

        # print('-- {} Order Candle Info: O: {}, H: {}, L {}, C {}, bracket_high: {}, bracket_low: {}'.format(
        #     self.data.datetime.datetime(), self.data0.open[-1], self.data0.high[-1], self.data0.low[-1], self.data0.close[-1], entryPrice, entryPrice ))

        if self.tradeDirection == 'long':
            # Place Buy Limit for 50% of Range with SL below Range and TP at TPRR multiple of Risk
            slPrice = self.rangeLow - self.p.stopLossPadPips
            risk_pips = entryPrice - slPrice
            # print('-- {} Workout Order size for buy limit order. Risk pips:{}'.format(
            # self.data.datetime.datetime(), risk_pips))
            size = self.getsizer().getsizing(self.data0, isbuy=True, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice + risk_pips * self.p.tpRR#((entryPrice - self.rangeLow) * self.p.tpRR)
            if self.p.stoplossTrail:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=self.rangeLow, stopargs=dict(trailamount=risk_pips),
                                limitprice= tpPrice,
                                valid=order_valid)
                self.orefs.append(o.ref for o in ob)
            else:
                ob = self.buy_bracket(exectype=bt.Order.Limit,
                                    size=size,
                                    price=entryPrice,
                                    stopprice=self.rangeLow, #stopargs=dict(valid=child_order_valid),
                                    limitprice= tpPrice, #limitargs=dict(valid=child_order_valid),
                                    valid=order_valid)
                self.orefs.append(o.ref for o in ob)
            self.tradeDirection = None
            self.log('RH:{}, RL: {}. LONG: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))

        if self.tradeDirection == 'short':
            # Place Buy Limit for 50% of Range with SL below Range and TP at TPRR multiple of Risk
            slPrice = self.rangeHigh + self.p.stopLossPadPips
            risk_pips =  slPrice - entryPrice
            # risk_pips =  self.rangeHigh - self.entryPriceLevel
            # print('-- {} Workout Order size for sell limit order'.format(
            # self.data.datetime.datetime()))
            size = self.getsizer().getsizing(self.data0, isbuy=False, pips=risk_pips, price=entryPrice, exchange_rate=None)
            tpPrice= entryPrice - risk_pips * self.p.tpRR
            slPrice = self.rangeHigh
            if self.p.stoplossTrail:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopexec=bt.Order.StopTrail,
                                stopprice=slPrice, stopargs=dict(trailamount=risk_pips),
                                limitprice= tpPrice, 
                                valid=order_valid)
                self.orefs.append(o.ref for o in ob)
            else:
                ob = self.sell_bracket(exectype=bt.Order.Limit,
                                size=size,
                                price=entryPrice,
                                stopprice=slPrice, #stopargs=dict(valid=child_order_valid),
                                limitprice= tpPrice, #limitargs=dict(valid=child_order_valid),
                                valid=order_valid)
                self.orefs.append(o.ref for o in ob)
            self.tradeDirection = None
            self.log('RH:{}, RL: {}. SHORT: entryPrice: {}, SL: {:.2f}, TP: {:.2f}, Size: {:.2f}'.format(
                self.rangeHigh, self.rangeLow, entryPrice, slPrice, tpPrice , size))

    def next(self):
        if self.p.printlog and len(self) % 1000 == 0:
            self.log(self.data.close[0])
        
        self.evaluateRangeOrder()
        