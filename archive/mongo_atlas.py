from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import datetime

def connect_to_mongo_test():
    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
    uri = "mongodb+srv://beatsworking:TCRekAnzsC8WiRTR@cluster0.vrrl7bd.mongodb.net/?retryWrites=true&w=majority"
    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

def insert_mongoDB():
    from pymongo import MongoClient
    db = MongoClient().aggregation_example
    result = db.things.insert_many(
        [
            {"x": 1, "tags": ["dog", "cat"]},
            {"x": 2, "tags": ["cat"]},
            {"x": 2, "tags": ["mouse", "cat", "dog"]},
            {"x": 3, "tags": []},
        ]
    )

def query_data():
    from bson.son import SON
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": SON([("count", -1), ("_id", -1)])},
    ]
    import pprint
    pprint.pprint(list(db.things.aggregate(pipeline)))

def tz_aware_date():
    from bson.codec_options import CodecOptions
    db.times.find_one()['date']
    # datetime.datetime(2002, 10, 27, 14, 0)
    aware_times = db.times.with_options(codec_options=CodecOptions(
        tz_aware=True,
        tzinfo=pytz.timezone('US/Pacific')))
    result = aware_times.find_one()
    # datetime.datetime(2002, 10, 27, 6, 0,  
    #                 tzinfo=<DstTzInfo 'US/Pacific' PST-1 day, 16:00:00 STD>)

# connect_to_mongo_test()

class OHLCMongo():

    
    db=None
    client=None
    instrument=None
    timeframe=None
    collection=None

    def __init__(self, instrument, timeframe) -> None:
        self.instrument=instrument
        self.timeframe=timeframe
        self.collection = "OHLC_" + instrument +"_"+ timeframe

    def connect(self): 
        uri = "mongodb+srv://beatsworking:TCRekAnzsC8WiRTR@cluster0.vrrl7bd.mongodb.net/?retryWrites=true&w=majority"
        # Create a new client and connect to the server
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        # Send a ping to confirm a successful connection
        try:
            self.client.admin.command('ping')
            print(datetime.datetime.today().isoformat(" ","seconds"), ":","Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(datetime.datetime.today().isoformat(" ","seconds"), ":",e)

        self.db = self.client.get_database("OHLC_Data")
        print(datetime.datetime.today().isoformat(" ","seconds"),":", "Got your DB", self.db.name)

    def insertOHLCs(self, bars):
        # print("Called insertOHLCs with: ", len(bars), " Bars")

        result = self.db[self.collection].insert_many(bars, ordered=False)
        print(datetime.datetime.today().isoformat(" ","seconds"),":", "Inserted:", len(bars), "Bars, First Timestamp in Batch:", bars[0]["timestamp"])


