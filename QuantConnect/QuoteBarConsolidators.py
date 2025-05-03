class MultiTimeframeAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2023, 1, 1)
        self.set_end_date(2023, 12, 31)
        self.set_cash(100000)

        # Add a security
        self.symbol = self.add_equity("SPY", Resolution.MINUTE).symbol

        # Create a 30-minute consolidator
        thirty_minute_consolidator = TradeBarConsolidator(timedelta(minutes=30))
        thirty_minute_consolidator.data_consolidated += self.on_thirty_minute_data
        self.subscription_manager.add_consolidator(self.symbol, thirty_minute_consolidator)

        # Create a daily consolidator
        daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        daily_consolidator.data_consolidated += self.on_daily_data
        self.subscription_manager.add_consolidator(self.symbol, daily_consolidator)

    def on_thirty_minute_data(self, sender, bar):
        # Handle 30-minute data
        self.log(f"30-Minute Bar: {bar}")

    def on_daily_data(self, sender, bar):
        # Handle daily data
        self.log(f"Daily Bar: {bar}")

    def on_data(self, data):
        # Handle incoming data
        pass