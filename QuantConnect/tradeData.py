class tradeData:
        def __init__(self, symbol, slStrategy, tpStrategy, riskAmountPerTrade, entryBufferPips, stopLossBuffer, 
        pip, minLotSize, contractMultiplier, qc: QCAlgorithm):

            self.symbol = symbol
            self.slStrategy = slStrategy
            
            self.riskAmountPerTrade = riskAmountPerTrade
            self.entryBufferPips = entryBufferPips
            self.stopLossBuffer = stopLossBuffer
            self.pip = pip
            self.minLotSize = minLotSize
            self.contractMultiplier = contractMultiplier
            self.portfolio = qc.portfolio
            self.qc = qc
            self.quantity = 0

            self.tpStrategy = tpStrategy
            self.useTakeProfit = True
            self.useTPRR = True
            self.TPRR = 3
            self.TP1Proportion = 1
            self.TP1Pips = 30
            self.TP2Proportion = 0.2
            self.TP2Pips = 80
            self.TP1Ticket = None
 
        def adjust_limit_price(self, pip, price, round_up=True):
            precision = int(abs(min(math.log10(pip), 0)))
            roundedPrice = math.floor(price / pip) * pip
            roundedPrice = round(roundedPrice, precision)
            return roundedPrice

        def calculate_desired_quantity(self, riskPips):
            security = self.qc.securities[self.symbol]

            minTick =  self.pip #security.SymbolProperties.minimum_price_variation
            contract_multiplier = self.contractMultiplier #security.SymbolProperties.contract_multiplier
            minPositionSize = self.minLotSize #security.SymbolProperties.lot_size

            # minPositionSize = lotSize#(minTick * lotSize)
            
            precision = int(abs(min(math.log10(minPositionSize), 0)))
            riskAmount = self.riskAmountPerTrade

            pipValue = minTick * contract_multiplier * minPositionSize

            rawOrderSize = riskAmount / (riskPips * pipValue)
            orderSize = math.floor(rawOrderSize / minPositionSize) * minPositionSize
            orderSize = round(orderSize, precision)

            parameter = InitialMarginParameters(security, orderSize)
            initial_margin = security.buying_power_model.get_initial_margin_requirement(parameter)

            if self.portfolio.margin_remaining < initial_margin.value:
                orderSize = 0
                self.qc.debug("You don't have sufficient margin for this order.")
            return orderSize

        def prepareTrade(self, long, entryPrice, invalidationPrice, barTime, spread):
            self.long = long
            self.entryPrice = entryPrice
            self.invalidationPrice = invalidationPrice

            if self.long:
                self.limitEntryPrice = self.adjust_limit_price(self.pip, entryPrice + (self.entryBufferPips * self.pip))
                self.stopLossPrice = self.adjust_limit_price(self.pip, invalidationPrice - (self.stopLossBuffer * self.pip) - spread)
                self.riskPips = int(((self.limitEntryPrice - self.stopLossPrice) / self.pip)) + 1
            else:
                self.limitEntryPrice = self.adjust_limit_price(self.pip, entryPrice - (self.entryBufferPips * self.pip))
                self.stopLossPrice = self.adjust_limit_price(self.pip, invalidationPrice + (self.stopLossBuffer * self.pip) + spread)
                self.riskPips = int(((self.stopLossPrice - self.limitEntryPrice) / self.pip)) + 1

            # work out quantity
            self.quantity  = self.calculate_desired_quantity(self.riskPips)
        
            if self.quantity == 0: self.qc.debug(f'Order Size ZERO @{self.qc.time}, bar time:{barTime}, entryPrice:{entryPrice}, invalidationPrice:{invalidationPrice}, limitEntryPrice: {self.limitEntryPrice}, stopLossPrice: {self.stopLossPrice}, quant: {self.quantity}')
            # self.qc.debug(f'@{self.qc.time}, bar time:{barTime}, sig_data.symbol: {self.symbol}, quantity: {self.quantity}, limitEntryPrice: {self.limitEntryPrice}, stopLossPrice: {self.stopLossPrice}')
            
        def placeOrder(self):
            self.qc.liquidate()
            self.qc.transactions.cancel_open_orders()

            # Place order
            if self.long:
                self.entryTicket = self.qc.limit_order(self.symbol, self.quantity, self.limitEntryPrice, 'Long Limit Entry Order') 
            else:
                self.entryTicket = self.qc.limit_order(self.symbol, -self.quantity, self.limitEntryPrice, 'Short Limit Entry Order')

        def calulateTPPrice(self, entryPrice, riskPips, pip, long):
            if self.useTPRR:
                tpPips = self.TPRR * riskPips
            else:
                tpPips = self.TP1Pips

            if long:
                tpPrice = entryPrice + (tpPips * pip)     
            else:
                tpPrice = entryPrice - (tpPips * pip)
            
            precision = int(abs(min(math.log10(pip), 0)))
            roundedPrice = math.floor(tpPrice / pip) * pip
            roundedPrice = round(roundedPrice, precision)
            return roundedPrice
        
        def calulateTPQuantity(self, quantity, minLotSize, TPProportion, long):
            orderPrecision = int(abs(min(math.log10(minLotSize), 0)))
            orderSize = max(round(abs(quantity) * TPProportion, orderPrecision), minLotSize)
            if long:
                orderSize = -orderSize
            return orderSize

        def exitTrade(self, msg, liquidate=False):
            if liquidate:
                self.qc.liquidate()
                self.qc.debug(msg)
            self.qc.transactions.cancel_open_orders()
            self.entryTicket = None
            self.stopLossTicket = None
            self.longStopLossTicket = None
            self.TP1Ticket = None
            self.highestPriceInLongPosition = 0
            self.lowestPriceInShortPosition = float('inf')
            self.riskPips = 0
            

        def handleOrderEvent(self, orderEvent: OrderEvent):
            # if not filled then exit
            # if long/short Entry then place SL and TP according to Strategy - TODO: Extract into class for injection later
            if orderEvent.status != OrderStatus.FILLED:
                return
         
            if self.entryTicket is not None and self.entryTicket.OrderId == orderEvent.OrderId:
                self.qc.debug(f'entered long:{self.long} - {self.qc.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')
                self.stopLossTicket = self.qc.stop_market_order(self.symbol, -self.entryTicket.quantity, self.stopLossPrice, 'Stop Loss Exit Order')

                if self.useTakeProfit:
                    tp1_quantity = self.calulateTPQuantity(self.entryTicket.quantity, self.minLotSize, self.TP1Proportion, self.long)
                    tp1_price = self.calulateTPPrice(orderEvent.fill_price, self.riskPips, self.pip, self.long)
                    # self.debug(f'setting Long TP1: {tp1_price}, qty: {tp1_quantity}')
                    self.TP1Ticket = self.qc.limit_order(self.symbol, tp1_quantity, tp1_price)
                    
                    # if not self.useTPRR:
                    #     tp2_quantity = -self._calculate_TP_quantity(self.securities[self._symbol], self.longEntryTicket.quantity, self.TP2Proportion)
                    #     remainingQty = abs(self.longEntryTicket.quantity) - abs(tp1_quantity)
                    #     if remainingQty > 0:
                    #         if tp2_quantity > remainingQty:
                    #             tp2_quantity = -remainingQty                
                    #         tp2_price = self._calculate_TP_Price(self.securities[self._symbol], orderEvent.fill_price, self.TP2Pips, True)
                    #         self.debug(f'setting Long TP2: {tp2_price}, qty: {tp2_quantity}')
                    #         self.longTP2Ticket = self.limit_order(self._symbol, tp2_quantity, tp2_price)
            if self.stopLossTicket is not None and self.stopLossTicket.OrderId == orderEvent.OrderId:
                msg = f'sl hit, long:{self.long} - {self.qc.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}'
                self.exitTrade(msg, liquidate=True)

            if self.TP1Ticket is not None and self.TP1Ticket.OrderId == orderEvent.OrderId:
                # update long SL
                if self.portfolio[orderEvent.symbol].invested:
                    updateFields = qc.UpdateOrderFields()
                    updateFields.quantity = -self.qc.portfolio[orderEvent.symbol].quantity #self.longStopLossTicket.quantity - orderEvent.fill_quantity
                    self.qc.debug(f'Adjust SL (TP1), long:{self.long} - {self.qc.time}, price: {orderEvent.fill_price}, qty: {updateFields.quantity}')
                    self.stopLossTicket.update(updateFields)
                else:
                    self.qc.transactions.cancel_open_orders()
                    self.stopLossTicket = None
                self.TP1Ticket = None
                self.qc.debug(f'tp hit, long:{self.long} - {self.qc.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')

            # if self.longTP2Ticket is not None and self.longTP2Ticket.OrderId == orderEvent.OrderId:
            #     if self.portfolio[orderEvent.symbol].invested:
            #         updateFields = UpdateOrderFields()
            #         updateFields.quantity = -self.portfolio[orderEvent.symbol].quantity #self.shortStopLossTicket.quantity - orderEvent.fill_quantity
            #         self.debug(f'Adjust Long SL (TP2): {orderEvent.fill_price}, qty: {updateFields.quantity}')
            #         self.longStopLossTicket.update(updateFields)
            #     else:
            #         self.transactions.cancel_open_orders()
            #         self.longStopLossTicket = None
            #     self.longTP2Ticket = None
            #     self.debug(f'long tp2 hit {self.time} @ {orderEvent.fill_price}, qty: {orderEvent.fill_quantity}')