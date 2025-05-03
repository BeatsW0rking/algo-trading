# region imports
from AlgorithmImports import *
from EntryManagement.TradeData import TradeData
# endregion

class SwimmingBlueBuffalo(QCAlgorithm):

    class signalDataTF:
        def __init__(self, symbol, tf):
            self.symbol = symbol
            self.tf = tf
        
            self.priorBar = None
            self.currentBar = None
            self.bearCSDBar = None
            self.bullCSDBar = None
            self.isPriorBar_BearExpansionBar = None
            self.isPriorBar_BullExpansionBar = None
            self.isBullExpansionBar = None
            self.isBearExpansionBar = None
            self.watchforBearCSD = None
            self.watchforBullCSD = None
            self.bullOBCandidate = None
            self.bearOBCandidate = None

            self.shortSignal = False
            self.longSignal = False
            self.scratchSignal = False
            self.orderPrepared = False

            self.priorH1High = None
            self.priorH1Low = None
            self.currentH1Highest = None
            self.currentH1Lowest = None
            self.sweptPriorH1High = False
            self.sweptPriorH1Low = False
            self.sweptPriorH1At = None
            self.currentH1Open = None
            self.signalValid = False # To track if the Current H1 is a valid bar for searching for Signals - The Open eneeds to fall within the priro bars Range

    def initialize(self):
        self.SetStartDate(2024, 4, 1)  # Set Start Date
        self.set_end_date(2024, 5, 1)
        self.SetCash(100000)  # Set Strategy Cash
        
        self.hoursOfBusiness = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        self.minutesOfBusiness = range(0,60) #[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        riskAmountPerTrade = 10
        entryBufferPips = 0 #1
        stopLossBuffer = 0 #2
        # self.AddCfd("DE30EUR", Resolution.Minute, Market.Oanda)
        
        nas = self.AddCfd("NAS100USD", Resolution.SECOND, Market.Oanda).symbol
        # self._symbol = self.AddCfd("XAGUSD", Resolution.SECOND, Market.Oanda).symbol
        
        nas_lot_size = self.Securities[nas].SymbolProperties.LotSize
        nas_pip = self.Securities[nas].SymbolProperties.minimum_price_variation
        nas_contract_multiplier = self.Securities[nas].SymbolProperties.contract_multiplier

        self.set_brokerage_model(BrokerageName.OANDA_BROKERAGE, AccountType.MARGIN)

        # Create a 1-minute consolidator
        self.consolidator = self.consolidate(nas, timedelta(minutes=1), self.on_one_minute_data)
        # Create a 5-minute consolidator
        self.consolidator = self.consolidate(nas, timedelta(minutes=5), self.on_five_minute_data)
        # Create a 15-minute consolidator
        self.consolidator = self.consolidate(nas, timedelta(minutes=15), self.on_fifteen_minute_data)
        # Create a 1-hour consolidator
        self.consolidator = self.consolidate(nas, timedelta(hours=1), self.on_one_hour_data)

        m1 = self.signalDataTF(nas, self.m1_tf)
        # m5 = self.signalDataTF(nas, self.m5_tf)
        # m15 = self.signalDataTF(nas, self.m15_tf)
        # h1 = self.signalDataTF(nas, self.h1_tf)

        self.signalData = {m1.tf: m1} #, m5.tf:m5, m15.tf:m15, h1.tf:h1}
        slStrategy = ''
        tpStrategy = ''
        self.tradeMgr = TradeData(nas, slStrategy, tpStrategy, riskAmountPerTrade, entryBufferPips, stopLossBuffer, nas_pip, nas_lot_size, nas_contract_multiplier, self)

    def on_one_minute_data(self, bar: TradeBar) -> None:
        # Handle 1-minute data
        # self.log(f"1-Minute Bar: {bar}")
        sig_data = self.signalData[self.m1_tf]
        self.evaluateSignalsCSD(sig_data, bar)
        self.evaluateMainSignals(sig_data, bar)
        self.joinSignals(sig_data, bar)
        spread = bar.ask.close - bar.bid.close
        self.executeTrades(spread)
        # pass
        
    def on_five_minute_data(self, bar: TradeBar) -> None:
        # Handle 5-minute data
        # self.log(f"5-Minute Bar: {bar}")
        # sig_data = self.signalData[self.m5_tf]
        # self.evaluateSignals(sig_data, bar)
        # spread = bar.ask.close - bar.bid.close
        # self.executeTrades(spread)
        pass
    
    def on_fifteen_minute_data(self, bar: TradeBar) -> None:
        # Handle 15-minute data
        # self.log(f"15-Minute Bar: {bar}")
        # sig_data = self.signalData[self.m15_tf]
        # spread = bar.ask.close - bar.bid.close
        # self.evaluateSignals(sig_data, bar)
        # self.executeTrades(spread)
        pass

    def on_one_hour_data(self, bar: TradeBar) -> None:
        # Handle 1-hour data
        # self.log(f"1-Hour Bar: {bar}")
        # sig_data = self.signalData[self.h1_tf]
        # self.evaluateMainSignals(sig_data, bar)

        # Reset Signal:
        sig_data = self.signalData[self.m1_tf]
        self.resetSignal(sig_data, TradeBar)
        pass

    def on_data(self, data: Slice):
        # if data.contains_key(self._symbol):
        #     data = slice[self._symbol]
        # else:
        #     return
        pass

    def resetSignal(self, sigData: signalDataTF, HTFbar: TradeBar):
        sigData.priorH1High = HTFbar.High
        sigData.priorH1Low = HTFbar.Low
        sigData.currentH1Highest = None
        sigData.currentH1Lowest = None
        sigData.sweptPriorH1High = False
        sigData.sweptPriorH1Low = False
        sigData.sweptPriorH1At = None
        sigData.currentH1Open = None
        sigData.signalValid = False

        # CSD Part:
        sigData.priorBar = None
        sigData.currentBar = None
        sigData.bearCSDBar = None
        sigData.bullCSDBar = None
        sigData.isPriorBar_BearExpansionBar = None
        sigData.isPriorBar_BullExpansionBar = None
        sigData.isBullExpansionBar = None
        sigData.isBearExpansionBar = None
        sigData.watchforBearCSD = None
        sigData.watchforBullCSD = None
        sigData.bullOBCandidate = None
        sigData.bearOBCandidate = None

        sigData.shortSignal = False
        sigData.longSignal = False
        sigData.scratchSignal = False
        sigData.orderPrepared = False

    def joinSignals(self, sigData: signalDataTF, bar: TradeBar):
        tradeMgr = self.tradeMgr

        if sigData.sweptPriorH1High and sigData.shortSignal and sigData.signalValid:
            # if the prior H1 Hagh has been swept and we have a Bearish CSD and we have not traded back tot the current H1 Open yet aka we have a Valid Signal
            # Set the Trade Parameters... Short
            sigData.shortSignal = False
            if self.time.hour in self.hoursOfBusiness and not self.portfolio.invested: #and sig_data_htf.shortSignal
                tradeMgr.prepareTrade(
                    long=False, 
                    entryPrice=sigData.bearOBCandidate.open, 
                    invalidationPrice=sigData.bearOBCandidate.high, 
                    barTime=sigData.currentBar.time, 
                    spread=spread,
                    tpPrice=sigData.currentH1Open,
                    useTPRR=False)
                sigData.orderPrepared = True
        
        if sigData.sweptPriorH1Low and sigData.longSignal and sigData.signalValid:
            # if the prior H1 Low has been swept and we have a Bullsih CSD and we have not traded back tot the current H1 Open yet aka we have a Valid Signal
            # Set the Trade Parameters... Long
            sigData.longSignal = False
            if self.time.hour in self.hoursOfBusiness and not self.portfolio.invested:
                tradeMgr.prepareTrade(
                    long=True, 
                    entryPrice=sigData.bullOBCandidate.open, 
                    invalidationPrice=sigData.bullOBCandidate.low, 
                    barTime=sigData.currentBar.time, 
                    spread=spread,
                    tpPrice=sigData.currentH1Open,
                    useTPRR=False)
                sigData.orderPrepared = True

    def evaluateMainSignals(self, sigData: signalDataTF, bar: TradeBar):
        # Have we traded Above or Below Prior H1 High or Low = Swept defintion for now

        if self.time.minute == 0 and self.time.hour in self.hoursOfBusiness:
            # Start of New H1 Bar. Set Open, Highest and Lowest
            sigData.currentH1Highest = bar.High
            sigData.currentH1Lowest = bar.Low
            sigData.currentH1Open = bar.Open
            if sigData.currentH1Open > sigData.priorH1Low and sigData.currentH1Open < sigData.priorH1High:
                sigData.signalValid = True

        if TradeBar.Low < sigData.priorH1Low and not sigData.sweptPriorH1High and not sigData.sweptPriorH1Low and self.time.minute in self.minutesOfBusiness and sigData.signalValid:
            # We have Swept a H1 Low that has not had the H1 High Swept or already trade Belwo the Prior H1 Low within the first x Min of the H1 Bar
            sigData.sweptPriorH1Low = True
            sigData.sweptPriorH1At = self.time
        
        if TradeBar.High > sigData.priorH1High and not sigData.sweptPriorH1High and not sigData.sweptPriorH1Low and self.time.minute in self.minutesOfBusiness and sigData.signalValid:
            # We have Swept a H1 Low that has not had the H1 High Swept or already trade Belwo the Prior H1 Low within the first x Min of the H1 Bar
            sigData.sweptPriorH1High = True
            sigData.sweptPriorH1At = self.time
        
        if bar.High > sigData.currentH1Highest:
            sigData.currentH1Highest = bar.High
        
        if bar.Low < signData.currentH1Lowest:
            sigData.currentH1Lowest = bar.Low

        if sigData.sweptPriorH1High and sigData.currentH1Lowest <= sigData.currentH1Open:
            # If the Current H1 price has alredy come back to the Current H1 Open then the Signal is not valid.
            # TODO: Look to add some padding here to make it a valid trade - not worth trading for x pts.
            sigData.signalValid = False

        if sigData.sweptPriorH1Low and sigData.currentH1Highest >= sigData.currentH1Open:
            # If the Current H1 price has alredy come back to the Current H1 Open then the Signal is not valid.
            # TODO: Look to add some padding here to make it a valid trade - not worth trading for x pts.
            sigData.signalValid = False

    # TODO: Extract into Library for CSD Entry on Main Signal...
    def evaluateSignalsCSD(self, sig_data: signalDataTF, bar: TradeBar):
        sig_data.priorBar = sig_data.currentBar
        sig_data.currentBar = bar

        if sig_data.priorBar is None:
            return

        # When to reset the bearishCSD and bullishCSD bars to None??? For now when an opposite is found 
        # TODO - need to sort out logic here to make sure that the OB cndidate persists once we are looking for CSD

        sig_data.isPriorBar_BearExpansionBar = sig_data.isBearExpansionBar
        sig_data.isBearExpansionBar = self.isBearExpansionBar(sig_data.priorBar, sig_data.currentBar)

        sig_data.isPriorBar_BullExpansionBar = sig_data.isBullExpansionBar
        sig_data.isBullExpansionBar = self.isBullExpansionBar(sig_data.priorBar, sig_data.currentBar)

        if sig_data.watchforBearCSD and sig_data.currentBar.close > sig_data.bearOBCandidate.high:
            sig_data.bearOBCandidate = None
            sig_data.watchforBearCSD = False
            sig_data.shortSignal = False
            sig_data.scratchSignal = True

        if sig_data.watchforBullCSD and sig_data.currentBar.close < sig_data.bullOBCandidate.low:
            sig_data.bullOBCandidate = None
            sig_data.watchforBullCSD = False
            sig_data.longSignal = False
            sig_data.scratchSignal = True

        if sig_data.isPriorBar_BullExpansionBar and not sig_data.isBullExpansionBar and not sig_data.watchforBearCSD: #Expansion has finished - look for CSD
            sig_data.bearOBCandidate = sig_data.priorBar
            sig_data.watchforBearCSD = True
            sig_data.watchforBullishCSD = False #Stop looking for Bullish CSD
        
        if sig_data.isPriorBar_BearExpansionBar and not sig_data.isBearExpansionBar and not sig_data.watchforBullCSD: #Expansion has finished - look for CSD
            sig_data.bullOBCandidate = sig_data.priorBar
            sig_data.watchforBullCSD = True
            sig_data.watchforBearCSD = False #Stop looking for Bearish CSD

        if sig_data.watchforBearCSD:
             if self.isBearishCSD(sig_data.bearOBCandidate, sig_data.currentBar) and not sig_data.shortSignal:
                sig_data.bearCSDBar = sig_data.currentBar
                sig_data.watchforBearCSD = False
                sig_data.bullCSDBar = None
                # sig_data.bullOBCandidate = None
                if sig_data.bearOBCandidate is None:
                    #Something is wrong
                    self.debug(f'ARGGHH - sig_data: tf: {sig_data.tf}, sig_data.bearcsd: {sig_data.bearCSDBar}, currentBar: {sig_data.currentBar}')
            
                sig_data.shortSignal = True
                sig_data.longSignal = False
                # self.debug(f"Signal to go Short @{self.time}. OB Candidate: {sig_data.bearOBCandidate.time}, CSD: {sig_data.bearCSDBar.time} - Price: {sig_data.bearOBCandidate.open}")
                # look to short at the candidate OB Open        
        
        if sig_data.watchforBullCSD:
             if self.isBullishCSD(sig_data.bullOBCandidate, sig_data.currentBar) and not sig_data.longSignal:
                sig_data.bullCSDBar = sig_data.currentBar
                sig_data.watchforBullCSD = False
                sig_data.bearCSDBar = None
                # sig_data.bearOBCandidate = None
                sig_data.longSignal = True
                sig_data.shortSignal = False
                # self.debug(f"Signal to go Long @{self.time}. OB Candidate: {sig_data.bullOBCandidate.time}, CSD: {sig_data.bullCSDBar.time} - Price: {sig_data.bullOBCandidate.open}")
                #look to long at CandidateOB Open

    def isBullishCSD(self, candidateOB: TradeBar, subjectBar: TradeBar):
        if subjectBar.close > candidateOB.open:
            return True
        else:
            return False      
    
    def isBearishCSD(self, candidateOB: TradeBar, subjectBar: TradeBar):
        if subjectBar.close < candidateOB.open:
            return True
        else:
            return False

    def isBullExpansionBar(self, priorBar: TradeBar, currentBar: TradeBar) -> bool:
        if currentBar.close > priorBar.high and currentBar.close > currentBar.open:
            return True
        else:
            return False 

    def isBearExpansionBar(self, priorBar: TradeBar, currentBar: TradeBar) -> bool:
        if currentBar.close < priorBar.low and currentBar.close < currentBar.open:
            return True
        else:
            return False 

    def executeTrades(self, spread):
        sig_data = self.signalData[self.m1_tf] 
        tradeMgr = self.tradeMgr

        if sig_data.scratchSignal and not self.portfolio.invested:
            sig_data.scratchSignal = False
            tradeMgr.exitTrade(f'scratch Signal: {self.time}')

        if sig_data.orderPrepared:
            sig_data.orderPrepared = False
            tradeMgr.placeOrder()


    def OnOrderEvent(self, orderEvent: OrderEvent):
        self.tradeMgr.handleOrderEvent(orderEvent)