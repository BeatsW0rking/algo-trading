
# region imports
from AlgorithmImports import *
import math
# endregion

class SleepyFluorescentPinkCrocodile(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2024, 1, 1)  # Set Start Date
        self.set_end_date(2025, 2, 14)
        self.SetCash(100000)  # Set Strategy Cash
        # self.AddCfd("DE30EUR", Resolution.Minute, Market.Oanda)
        
        self._symbol = self.AddCfd("NAS100USD", Resolution.SECOND, Market.Oanda).symbol
        # self._symbol = self.AddCfd("XAGUSD", Resolution.SECOND, Market.Oanda).symbol
        
        self.lot_size = self.Securities[self._symbol].SymbolProperties.LotSize
        self.set_brokerage_model(BrokerageName.OANDA_BROKERAGE, AccountType.MARGIN)

        self.longEntryTicket = None
        self.shortEntryTicket = None
        self.longStopLossTicket = None
        self.shortStopLossTicket = None
        self.longTP1Ticket = None
        self.shortTP1Ticket = None
        self.longTP2Ticket = None
        self.shortTP2Ticket = None

        self.longStopEntryPrice = 0
        self.shortStopEntryPrice = 0
        self.longStopLossPrice = 0
        self.shortStopLossPrice = 0

        self.entryTime = datetime.min
        self.entryBufferPips = 2
        self.stopLossBuffer = 5
        self.riskAmount = 20
        self.hoursOfBusiness = [2, 3, 4, 7, 10, 11, 12, 13, 14, 16, 18, 20]
        self.minuteLow = float('inf')
        self.minuteHigh = 0
        self.riskPips = 0

        self.minuteExit = 59
        self.useTakeProfit = True
        self.useTPRR = True
        self.TPRR = 6
        self.TP1Proportion = 0.5
        self.TP1Pips = 30
        self.TP2Proportion = 0.2
        self.TP2Pips = 80

        self.useTrailingStopLoss = True
        self.highestPriceInLongPosition = 0
        self.lowestPriceInShortPosition = float('inf')
        self.trailingStopPips = 400


    def _adjust_limit_price(self, security, price, round_up=True):
        # pip = security.price_variation_model.get_minimum_price_variation(
        #     GetMinimumPriceVariationParameters(security, price)
        # )
        pip = security.SymbolProperties.minimum_price_variation
        # precision = int(math.log10(1 / pip))
        # roundedPrice = round(price, precision)
        roundedPrice = math.floor(price / pip) * pip
        # return (int(price / pip) + int(round_up)) * pip
        return roundedPrice

    def _calculate_deisred_quantity(self, security, riskPips):
        minTick = security.SymbolProperties.minimum_price_variation
        contract_multiplier = security.SymbolProperties.contract_multiplier
        lotSize = security.SymbolProperties.lot_size

        minPositionSize = (minTick * lotSize)
        riskAmount = self.riskAmount

        pipValue = minTick * contract_multiplier * lotSize

        rawOrderSize = riskAmount / (riskPips * pipValue)
        orderSize = math.floor(rawOrderSize / minPositionSize) * minPositionSize

        parameter = InitialMarginParameters(security, orderSize)
        initial_margin = security.buying_power_model.get_initial_margin_requirement(parameter)

        if self.portfolio.margin_remaining < initial_margin.value:
            orderSize = 0
            self.debug("You don't have sufficient margin for this order.")
        #contract_multiplier	minimum_price_variation	lot_size

        # orderPrecision = int(math.log10(1 / minTick))

        # orderSize = round(riskAmount / (riskPips * minTick), orderPrecision)


        # self.debug(f'orderSize: {orderSize}, riskPips: {riskPips}, minTick: {minTick}')
        # look at max size for margin
        # maxPositionSize = math.round((accountBalance * (1 - i_saftey_factor)) / (entryPrice * i_marginRatio), orderPrecision)

        # orderSize := math.min(maxPositionSize, orderSize)
        
        return orderSize #self.calculate_order_quantity(self._symbol, 0.9)

    def exitTrade(self, msg, liquidate=False):
        self.liquidate()
        self.transactions.cancel_open_orders()
        self.longEntryTicket = None
        self.shortEntryTicket = None
        self.shortStopLossTicket = None
        self.longStopLossTicket = None
        self.longTP1Ticket = None
        self.shortTP1Ticket = None
        self.longTP2Ticket = None
        self.shortTP2Ticket = None
        self.highestPriceInLongPosition = 0
        self.lowestPriceInShortPosition = float('inf')
        self.riskPips = 0
        self.debug(msg)

    def OnData(self, slice: Slice):
        if slice.contains_key(self._symbol):
            data = slice[self._symbol]
        else:
            return

        _security = self.securities[self._symbol]

        # Track Levels:
        if self.time.minute == 0 and self.time.hour in self.hoursOfBusiness:
            self.minuteLow = min(self.minuteLow, data.low)
            self.minuteHigh = max(self.minuteHigh, data.high)
        # if self.portfolio.invested:
        #     self.highestPriceInLongPosition = max(self.highestPrice, data.high)
        #     self.lowestPriceInShortPosition = min(self.lowestPriceInShortPosition, data.low)
        minTick = _security.SymbolProperties.minimum_price_variation
        spread = data.ask.close - data.bid.close
        
        #Entry Signal?
        if not self.portfolio.invested and self.time.second == 1 and self.time.minute == 1 and self.time.hour in self.hoursOfBusiness: #Time is the start of the next Interval not the end of the current one (so to bracket M0 we need to look for M1)
            


            high = self.minuteHigh
            low = self.minuteLow

            self.highestPriceInLongPosition = high
            self.lowestPriceInShortPosition = low
            # self.debug(f'spread: {spread}')

            # need to track highest and lowest over the last minute (when using second level data)
            self.longStopEntryPrice = self._adjust_limit_price(_security, high + (self.entryBufferPips * minTick))
            self.shortStopEntryPrice = self._adjust_limit_price(_security, low - (self.entryBufferPips * minTick))

            self.longStopLossPrice = self._adjust_limit_price(_security, low - (self.stopLossBuffer * minTick) - spread)
            self.shortStopLossPrice = self._adjust_limit_price(_security, high + (self.stopLossBuffer * minTick) + spread)

            self.riskPips = int(((self.longStopEntryPrice - self.longStopLossPrice) / minTick)) + 1
            
            # work out quantity
            quantity = self._calculate_deisred_quantity(_security, self.riskPips)
            self.debug(f'Entry @{self.time}, bar time:{data.end_time}, high:{high}, low:{low}, longStopEntryPrice: {self.longStopEntryPrice}, shortStopEntryPrice: {self.shortStopEntryPrice}, quant: {quantity}, spread: {spread}')
            
            if quantity == 0: self.debug(f'Order Size ZERO @{self.time}, bar time:{data.end_time}, high:{high}, low:{low}, longStopEntryPrice: {self.longStopEntryPrice}, shortStopEntryPrice: {self.shortStopEntryPrice}, quant: {quantity}')
            # Bracket M0 Bar High and Low with Buffer
            self.longEntryTicket = self.stop_market_order(self._symbol, quantity, self.longStopEntryPrice, 'Long Bracket Entry Order')
            self.shortEntryTicket = self.stop_market_order(self._symbol, -quantity, self.shortStopEntryPrice, 'Short Bracket Entry Order')
            # self.debug(f'Placed Bracket at: {self.time}, bar time:{data.end_time}, high:{high}, low:{low}, longStopEntryPrice: {self.longStopEntryPrice}, shortStopEntryPrice: {self.shortStopEntryPrice}, quant: {quantity}')

            self.minuteLow = float('inf')
            self.minuteHigh = 0

        # Move Trailing Stop Loss
        price = data.price
        if self.useTrailingStopLoss and self.longStopLossTicket is not None and self.portfolio.invested:
            # If Price has moved up X Pips then move SL up to Y Pips below price
            if price > self.highestPriceInLongPosition:
                self.highestPriceInLongPosition = price
                updateFields = UpdateOrderFields()
                updateFields.stop_price = max(self.longStopLossPrice, self._adjust_limit_price(_security, price - (self.trailingStopPips * minTick) - spread)) #(self.longStopEntryPrice - self.longStopLossPrice)) #self.longStopLossTicket.get(OrderField.STOP_PRICE)
                self.longStopLossTicket.update(updateFields)
                self.debug(updateFields.stop_price)
        if self.useTrailingStopLoss and self.shortStopLossTicket is not None and self.portfolio.invested:
            if price < self.lowestPriceInShortPosition:
                self.lowestPriceInShortPosition = price
                updateFields = UpdateOrderFields()
                updateFields.stop_price = min(self.shortStopLossPrice, self._adjust_limit_price(_security, price + (self.trailingStopPips * minTick) + spread))#(self.shortStopEntryPrice - self.shortStopLossPrice)) #self.longStopLossTicket.get(OrderField.STOP_PRICE)
                self.shortStopLossTicket.update(updateFields)
                self.debug(updateFields.stop_price)

        # Exit position if it is in the portfolio for more than 45 minutes.
        if self.time.minute == self.minuteExit and (self.longEntryTicket is not None or self.shortEntryTicket is not None): #self.entryTicket.time + timedelta(minutes=58) < self.utc_time:
            msg = f'exited trade (Time)  {self.time} @ {_security.price}'
            self.exitTrade(msg, liquidate=True)


     # It will be triggered on live trading.
    def on_brokerage_message(self, message: BrokerageMessageEvent) -> None: 
        if message.type == BrokerageMessageType.ERROR:
            self.log(f"{self.time}: {message.type}: Message: {message.message}")

    def _calculate_TP_quantity(self, security, positionQuantity, TPProportion):
        minTick = security.SymbolProperties.minimum_price_variation
        orderPrecision = int(math.log10(1 / minTick))
        orderSize = max(round(abs(positionQuantity) * TPProportion, orderPrecision), minTick)
        return orderSize

    def _calculate_TP_Price(self, security, entryPrice, tpPips, long=True):
        minTick = security.SymbolProperties.minimum_price_variation
        tpPrice = 0
        if long:
            tpPrice = entryPrice + (tpPips * minTick)     
        else:
            tpPrice = entryPrice - (tpPips * minTick)
        return math.floor(tpPrice / minTick) * minTick

    def OnOrderEvent(self, orderEvent: OrderEvent):
        if orderEvent.status != OrderStatus.FILLED:
            return
         
        # If Long side of Bracket Filled then 
        # 1. kill other side of bracket
        # 2. send stop loss order for risk management
        if self.longEntryTicket is not None and self.longEntryTicket.OrderId == orderEvent.OrderId:
            self.debug(f'entered long {self.time} @ {orderEvent.fill_price}')
            self.shortEntryTicket.cancel('Cancel Short end of Bracket')
            self.longStopLossTicket = self.stop_market_order(self._symbol, -self.longEntryTicket.quantity, self.longStopLossPrice, 'Long Stop Loss Exit Order')

            if self.useTakeProfit:
                tp1_quantity = -self._calculate_TP_quantity(self.securities[self._symbol], self.longEntryTicket.quantity, self.TP1Proportion)
                if self.useTPRR:
                    tpPips = self.TPRR * self.riskPips
                else:
                    tpPips = self.TP1Pips
                tp1_price = self._calculate_TP_Price(self.securities[self._symbol], orderEvent.fill_price, tpPips, True)
                # self.debug(f'setting Long TP1: {tp1_price}, qty: {tp1_quantity}')
                self.longTP1Ticket = self.limit_order(self._symbol, tp1_quantity, tp1_price)
                
                if not self.useTPRR:
                    tp2_quantity = -self._calculate_TP_quantity(self.securities[self._symbol], self.longEntryTicket.quantity, self.TP2Proportion)
                    remainingQty = abs(self.longEntryTicket.quantity) - abs(tp1_quantity)
                    if remainingQty > 0:
                        if tp2_quantity > remainingQty:
                            tp2_quantity = -remainingQty                
                        tp2_price = self._calculate_TP_Price(self.securities[self._symbol], orderEvent.fill_price, self.TP2Pips, True)
                        self.debug(f'setting Long TP2: {tp2_price}, qty: {tp2_quantity}')
                        self.longTP2Ticket = self.limit_order(self._symbol, tp2_quantity, tp2_price)
                    

        # If Short side of Bracket Filled then 
        # 1. kill other side of bracket
        # 2. send stop loss order for risk management
        if self.shortEntryTicket is not None and self.shortEntryTicket.OrderId == orderEvent.OrderId:
            self.debug(f'entered short {self.time} @ {orderEvent.fill_price}. qty:{orderEvent.fill_quantity}')
            self.longEntryTicket.cancel('Cancel Long end of Bracket')
            self.shortStopLossTicket = self.stop_market_order(self._symbol, -self.shortEntryTicket.quantity, self.shortStopLossPrice, 'Short Stop Loss Exit Order')

            if self.useTakeProfit:
                tp1_quantity = self._calculate_TP_quantity(self.securities[self._symbol], self.shortEntryTicket.quantity, self.TP1Proportion)
                if self.useTPRR:
                    tpPips = self.TPRR * self.riskPips
                else:
                    tpPips = self.TP1Pips
                tp1_price = self._calculate_TP_Price(self.securities[self._symbol], orderEvent.fill_price, tpPips, False)
                self.debug(f'setting Short TP1: {tp1_price}, qty: {tp1_quantity}')
                self.shortTP1Ticket = self.limit_order(self._symbol, tp1_quantity, tp1_price)

                if not self.useTPRR:
                    tp2_quantity = self._calculate_TP_quantity(self.securities[self._symbol], self.shortEntryTicket.quantity, self.TP2Proportion)
                    remainingQty = abs(self.shortEntryTicket.quantity) - abs(tp1_quantity)
                    if remainingQty > 0:
                        if tp2_quantity > remainingQty:
                            tp2_quantity = remainingQty 

                        tp2_price = self._calculate_TP_Price(self.securities[self._symbol], orderEvent.fill_price, self.TP2Pips, False)
                        self.debug(f'setting Short TP2: {tp2_price}, qty: {tp2_quantity}')
                        self.shortTP2Ticket = self.limit_order(self._symbol, tp2_quantity, tp2_price)
                
        if self.longStopLossTicket is not None and self.longStopLossTicket.OrderId == orderEvent.OrderId:
            msg = f'long stop hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}'
            self.exitTrade(msg, liquidate=True)

        if self.shortStopLossTicket is not None and self.shortStopLossTicket.OrderId == orderEvent.OrderId:
            msg = f'short stop hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}'
            self.exitTrade(msg, liquidate=True)

        if self.longTP1Ticket is not None and self.longTP1Ticket.OrderId == orderEvent.OrderId:
            # update long SL
            if self.portfolio[orderEvent.symbol].invested:
                updateFields = UpdateOrderFields()
                updateFields.quantity = -self.portfolio[orderEvent.symbol].quantity #self.longStopLossTicket.quantity - orderEvent.fill_quantity
                self.debug(f'Adjust Long SL (TP1): {orderEvent.fill_price}, qty: {updateFields.quantity}')
                self.longStopLossTicket.update(updateFields)
            self.longTP1Ticket = None
            self.debug(f'long tp hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')

        if self.shortTP1Ticket is not None and self.shortTP1Ticket.OrderId == orderEvent.OrderId:
            # update short SL
            if self.portfolio[orderEvent.symbol].invested:
                updateFields = UpdateOrderFields()
                updateFields.quantity = -self.portfolio[orderEvent.symbol].quantity #self.shortStopLossTicket.quantity - orderEvent.fill_quantity
                self.debug(f'Adjust Short SL (TP1): {orderEvent.fill_price}, qty: {updateFields.quantity}')
                self.shortStopLossTicket.update(updateFields)
            self.shortTP1Ticket = None
            self.debug(f'short tp hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')
        
        if self.longTP2Ticket is not None and self.longTP2Ticket.OrderId == orderEvent.OrderId:
            if self.portfolio[orderEvent.symbol].invested:
                updateFields = UpdateOrderFields()
                updateFields.quantity = -self.portfolio[orderEvent.symbol].quantity #self.shortStopLossTicket.quantity - orderEvent.fill_quantity
                self.debug(f'Adjust Long SL (TP2): {orderEvent.fill_price}, qty: {updateFields.quantity}')
                self.longStopLossTicket.update(updateFields)
            else:
                self.transactions.cancel_open_orders()
                self.longStopLossTicket = None
            self.longTP2Ticket = None
            self.debug(f'long tp2 hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')

        if self.shortTP2Ticket is not None and self.shortTP2Ticket.OrderId == orderEvent.OrderId:
            if self.portfolio[orderEvent.symbol].invested:
                updateFields = UpdateOrderFields()
                updateFields.quantity = -self.portfolio[orderEvent.symbol].quantity #self.shortStopLossTicket.quantity - orderEvent.fill_quantity
                self.debug(f'Adjust Short SL (TP2): {orderEvent.fill_price}, qty: {updateFields.quantity}')
                self.shortStopLossTicket.update(updateFields)
            else:
                self.transactions.cancel_open_orders()
                self.shortStopLossTicket = None
            self.shortTP2Ticket = None
            self.debug(f'short tp2 hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')


            