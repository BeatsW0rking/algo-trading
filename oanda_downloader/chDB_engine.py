import datetime
from chdb.session import Session


class OHLC_CHDB():

    
    db=None
    instrument=None
    timeframe=None

    def __init__(self, instrument, timeframe) -> None:
        self.instrument=instrument
        self.timeframe=timeframe

    def connect(self): 
        dbPath ="/tmp/oanda_data"
        print("Starting chDB...")
        # create a persistent session
        db = Session(dbPath)
        # db = Session()


        try:
            # create a database and a table
            db.query("create database IF NOT EXISTS quant")
            db.query("""
            create table IF NOT EXISTS quant.ohlc (
            instrument LowCardinality(String),
            tf LowCardinality(String),
            open Decimal(10,5),
            high Decimal(10,5),
            low Decimal(10,5),
            close Decimal(10,5),
            timestamp DateTime('EST'),
            ) engine MergeTree
            PRIMARY KEY (instrument, tf, timestamp);
            """)
        
            res = db.query("select count(*) from quant.ohlc")
            print(datetime.datetime.today().isoformat(" ","seconds"), ":","chDB", dbPath, "has", res, "rows" )
        except Exception as e:
            print(datetime.datetime.today().isoformat(" ","seconds"), ":",e)

        self.db = db
        print(datetime.datetime.today().isoformat(" ","seconds"),":", "Got your DB", dbPath)

    def insertOHLCs(self, bars):
        # print("Called insertOHLCs with: ", len(bars), " Bars")

        query = """INSERT INTO quant.ohlc (instrument, tf, open, high, low, close, timestamp) VALUES """

        values = [f"('{self.instrument}', '{self.timeframe}', {bar['open']}, {bar['high']}, {bar['low']}, {bar['close']}, '{bar['timestamp']}')" for bar in bars]

        seperator = ", "
        full_query = query + seperator.join(values) +";"

        # print(datetime.datetime.today().isoformat(" ","seconds"), ":", "Query:", full_query)
        res = self.db.query(full_query)


        print(datetime.datetime.today().isoformat(" ","seconds"),":", "Inserted:", len(bars),  "Bars, for: ", self.instrument, "First Timestamp in Batch:", bars[0]["timestamp"])
        res = self.db.query("select count(*) from quant.ohlc")
        print(datetime.datetime.today().isoformat(" ","seconds"), ":","chDB", "has", res, "rows" )
