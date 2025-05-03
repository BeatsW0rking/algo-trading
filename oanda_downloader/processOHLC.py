import chdb
from datetime import datetime, timedelta
from chdb.session import Session
import chdb.dataframe as cdf
from pathlib import Path
import time
from zoneinfo import ZoneInfo
import pandas as pd
pd.options.mode.copy_on_write = True
df = None

#Enrtry Points:

# runProcessRawPipeline()
    # dropOptimisedTable() - Drops the Table from the ChDb Instance
    # createOptimisedTable() - Create the Table to hold the sample data optimised for Pandas datatypes
    # insertSamplesIntoOptimisedTable() - Inserts teh Raw Samples into the new Table
    # exportToParquet() - Writes out the Optimised Table as a local Parquet File (Could be generalised?)
    # readbackParquetFile() - Test function to see if the paquet file can be read back succesfully
    # readbackSmallSample() - Test function to see if the paquet file can be read back succesfully
    # importFromPaquetintoDataFrame() - Reads the Parquet File into a dataframe and sets the correct types, timezones and index
    # writeOptimisedDataFrameAsParquet(dftemp) - used native DataFrame method to write out final data frame to preserve the df settings.

# runFullAggregationPipeline()
    # loadOptimisedSampleData() - REads in the Paruet File Writen at the end of the runProcessRawPipeline()
    # aggregate_samples_to_interval() - SQL Windowing function to aggregate the samples in the input df by the specified timeframe and get the sample timestamp when the High and Low were formed - reutrns a Clickhouse DB df result
    # storeIntermediateData() - Stores the current batch into an intermediate Parquet file for insertion into the final results set Table
    # insertOHLCs() - Writes the intermediate Parquet results file into a chDB Table
    # outputFinalDataSet() - Reads the whole chDB Results table for the instrument and timeframe and outputs the final Parquet file for further analysis

# GenerateDailyOHLC()
    # creates Daily Aligned OHLC Bars

def dropOptimisedTable():
    db = Session(path="/tmp/oanda_data")

    res = db.query("select count(*) from quant.ohlc_opt")
    print(res)
    db.query("drop table quant.ohlc_opt")
    
def createOptimisedTable():
    db = Session(path="/tmp/oanda_data")

    db.query("create database IF NOT EXISTS quant")
    db.query("""
                create table IF NOT EXISTS quant.ohlc_opt (
                instrument LowCardinality(String),
                tf LowCardinality(String),
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                timestamp DateTime64,
                ) engine MergeTree
                PRIMARY KEY (instrument, tf, timestamp);
                """)
    res = db.query("select count(*) from quant.ohlc_opt")
    print(res)
    
def insertSamplesIntoOptimisedTable():
    db = Session(path="/tmp/oanda_data")

    sql = """INSERT INTO quant.ohlc_opt (instrument, tf, open, high, low, close, timestamp) select instrument, tf,
            max(open) as open, max(high) as high, max(low) as low, max(close) as close, timestamp 
            from quant.ohlc group by instrument, tf, timestamp Order by timestamp desc"""
    res = db.query(sql)
    res = db.query("select count(*) from quant.ohlc_opt")
    print(res)
    
def exportToParquet():
    start = time.time()

    print("Starting chDB...")
    # create a persistent session
    db = Session(path="/tmp/oanda_data") #/tmp/quantDB")

    res = db.query("""select instrument, tf, max(open) as open, max(high) as high, max(low) as low, max(close) as close,
                   timestamp from quant.ohlc_opt group by instrument, tf, timestamp Order by timestamp desc""", "Parquet")

    print(
        f"{res.rows_read()} rows | "
        f"{res.bytes_read()} bytes | "
        f"{res.elapsed()} seconds"
    )

    # export to Parquet
    path = Path("./data/oanda_data_opt.parquet")
    path.write_bytes(res.bytes())

    end = time.time()
    print(end - start)
    
def readbackParquetFile():
    # Readback the file and see if it has the same number of rows
    db = Session()
    start = time.time()
    res = db.query("select * from './oanda_data_opt.parquet' order by timestamp desc", "Parquet")

    end = time.time()
    print(end - start)
    print(
        f"{res.rows_read()} rows | "
        f"{res.bytes_read()} bytes | "
        f"{res.elapsed()} seconds"
    )
    
def readbackSmallSample():
    # import from Parquet
    db = Session()

    query_sql = "select * from './data/oanda_data_opt.parquet' order by timestamp desc limit 5"
    res = chdb.query(query_sql, "PrettyCompactNoEscapes")
    print(res, end="")
    
def importFromPaquetintoDataFrame():
    # import from Parquet and convert to pandas/numpy data types
    db = Session()
    start = time.time()

    datafile = './data/oanda_data_opt.parquet'
    data = f"file('{datafile}', Parquet)"

    sql = f"""SELECT * FROM {data} order by timestamp desc"""

    dfETL = chdb.query(sql, 'Dataframe')

    # Sort out Data Types to work with Pandas / Numpy
    dfETL['instrument'] = dfETL['instrument'].astype(pd.StringDtype())
    dfETL['tf'] = dfETL['tf'].astype(pd.StringDtype())
    dfETL['timestamp'] = dfETL['timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    dfETL = dfETL.set_index(['timestamp'])

    end = time.time()
    print(end - start)

    print(dfETL)
    dfETL.describe(include='all')
    dfETL.info()
    return dfETL
    
def writeOptimisedDataFrameAsParquet(dfETL):    
    #Write out optimised dataframe as parquet
    start = time.time()
    dfFile = './data/oanda_data_pandas.parquet'
    dfETL.to_parquet(path=dfFile, index=True)
    end = time.time()
    print(end - start)
    dfETL = None
    
def runProcessRawPipeline():
    dropOptimisedTable()
    createOptimisedTable()
    insertSamplesIntoOptimisedTable()
    exportToParquet()
#     readbackParquetFile()
#     readbackSmallSample()
    dftemp = importFromPaquetintoDataFrame()
    writeOptimisedDataFrameAsParquet(dftemp)

def loadOptimisedSampleData(parquetFile):
    #Load optimised dataframe from parquet file
    start = time.time()
    dfFile = parquetFile #'./data/oanda_data_pandas.parquet'
    df = pd.read_parquet(path=dfFile)
    end = time.time()
    print("Loaded Optimised Sample Data:", end - start)
    return df

def clearOHLCTable():
    db = Session(path="/tmp/aggregated_oanda")
    
    db.query("truncate TABLE IF EXISTS quant.ohlc_agg")

def insertOHLCs(instrument, tf, parquetFile):

    data = f"file('{parquetFile}', Parquet)"
    db = Session(path="/tmp/aggregated_oanda")
    
    db.query("create database IF NOT EXISTS quant")
    
    db.query(f"""
    create table IF NOT EXISTS quant.ohlc_agg (
    instrument LowCardinality(String),
    tf LowCardinality(String),
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    interval DateTime64,
    high_timestamp DateTime64,
    low_timestamp DateTime64,
    first_sample DateTime64,
    last_sample DateTime64,
    samples UInt32  
    ) engine MergeTree
    PRIMARY KEY (instrument, tf, interval);
    """)

    query = f"""
    INSERT INTO quant.ohlc_agg (instrument, tf, open, high, low, close, high_timestamp, low_timestamp, interval, samples, first_sample, last_sample)

    select '{instrument}' as instrument, '{tf}' as tf, max(open) as open, max(high) as high, max(low) as low, max(close) as close, 
    max(high_timestamp) as high_timestamp, max(low_timestamp) as low_timestamp,
    interval, samples, first_sample, last_sample from {data} group by instrument, tf, interval, samples, first_sample, last_sample Order by interval
    """

    # query = f"""
    # INSERT INTO quant.ohlc_agg (instrument, tf, open, high, low, close, high_timestamp, low_timestamp, interval, samples, first_sample, last_sample)
     
    # select 
    # '{instrument}' as instrument, 
    # '{tf}' as tf, 
    # FIRST_VALUE(open) OVER (PARTITION BY interval ORDER BY samples desc) as open,
    # FIRST_VALUE(high) OVER (PARTITION BY interval ORDER BY samples desc) as high, 
    # FIRST_VALUE(low) OVER (PARTITION BY interval ORDER BY samples desc) as low, 
    # FIRST_VALUE(close) OVER (PARTITION BY interval ORDER BY samples desc) as close, 
    # FIRST_VALUE(high_timestamp) OVER (PARTITION BY interval ORDER BY samples desc) as high_timestamp, 
    # FIRST_VALUE(low_timestamp) OVER (PARTITION BY interval ORDER BY samples desc) as low_timestamp,
    # FIRST_VALUE(interval) OVER (PARTITION BY interval ORDER BY samples desc) as interval, 
    # FIRST_VALUE(samples) OVER (PARTITION BY interval ORDER BY samples desc) as samples, 
    # FIRST_VALUE(first_sample) OVER (PARTITION BY interval ORDER BY samples desc) as first_sample, 
    # FIRST_VALUE(last_sample) OVER (PARTITION BY interval ORDER BY samples desc) as last_sample  
    # from {data} 
    # Order by interval
    # """
    
    res = db.query(query)
#     res = cdf.query(sql=query, df=intermediate_df)

    res = db.query(f"select count(*) from quant.ohlc_agg where instrument='{instrument}' and tf='{tf}'")
    print(datetime.today().isoformat(" ","seconds"), ":","chDB", "has", res, "rows" )
    
def storeIntermediateData(instrument, tf, bars):
    # export to Parquet
    start = time.time()
    dfFile = f"./data/oanda_data_intermediate_{instrument}_{tf}.parquet"
    bars.to_parquet(path=dfFile, index=True)
    end = time.time()
    # print(end - start)
    return dfFile

def outputFinalDataSet(instrument, tf):
    db = Session(path="/tmp/aggregated_oanda")
    
    query = f"select * from quant.ohlc_agg where instrument='{instrument}' and tf='{tf}' order by interval"
    dfres = db.query(query, 'dataframe')
    
    dfres['instrument'] = dfres['instrument'].astype(pd.StringDtype())
    dfres['tf'] = dfres['tf'].astype(pd.StringDtype())
    dfres['high_timestamp']  = dfres['high_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    dfres['low_timestamp'] = dfres['low_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    dfres['first_sample'] = dfres['first_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    dfres['last_sample'] = dfres['last_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    
    # dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    if tf not in ['D1', 'W1', 'M']:
        dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    dfres = dfres.set_index(['interval'])
    if tf in ['D1', 'W1', 'M']:
        dfres.index = dfres.index.date


    start = time.time()
    dfFile = f'./data/oanda_{instrument}_{tf}.parquet'
    dfres.to_parquet(path=dfFile, index=True)
    end = time.time()
    print(end - start)
    dfres = None

def dropFinalResultschDB():
    db = Session(path="/tmp/aggregated_oanda")
    db.query("drop table quant.ohlc_agg")
    
def aggregate_samples_to_interval(sample_df, instrument, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, tzOffset, hours_skew=2):
    print(f'Calling aggregate_samples_to_interval with start: {start}, end: {end}, interval_bucket_size: {interval_bucket_size}, interval_bucket_type: {interval_bucket_type}, tzOffset: {tzOffset}')
    query_sql = f"""
    select sq.interval, max(sq.open), max(sq.high), max(sq.low), max(sq.close), max(sq.high_timestamp), max(sq.low_timestamp), max(sq.samples) as samples, max(sq.first_sample) as first_sample, max(sq.last_sample) as last_sample 
    from
        (select 
        {intervalAggregateTerm},
        FIRST_VALUE(s5.timestamp) OVER (PARTITION BY interval ORDER BY s5.timestamp asc) as first_sample,
        FIRST_VALUE(s5.timestamp) OVER (PARTITION BY interval ORDER BY s5.timestamp desc) as last_sample,
        FIRST_VALUE(s5.open) OVER (PARTITION BY interval ORDER BY s5.timestamp asc) open,
        FIRST_VALUE(s5.high) OVER (PARTITION BY interval ORDER BY s5.high desc) high,
        FIRST_VALUE(s5.low)  OVER (PARTITION BY interval ORDER BY s5.low asc) low,
        FIRST_VALUE(s5.close) OVER (PARTITION BY interval ORDER BY s5.timestamp desc) close,
        FIRST_VALUE(s5.timestamp) OVER (PARTITION BY interval ORDER BY s5.high desc, s5.timestamp) high_timestamp,
        FIRST_VALUE(s5.timestamp) OVER (PARTITION BY interval ORDER BY s5.low asc, s5.timestamp) low_timestamp,
        count(*) OVER (PARTITION BY interval) as samples 
        from __s5__ as s5
        where s5.instrument='{instrument}' and s5.timestamp >= toDateTime('{start}', '{tzOffset}') and s5.timestamp < toDateTime('{end}', '{tzOffset}')
        order by s5.timestamp
        ) as sq
    group by sq.interval, sq.open, sq.high , sq.low, sq.close, sq.high_timestamp, sq.low_timestamp, sq.samples, sq.first_sample, sq.last_sample
    order by sq.interval desc
    ;
    """
    res = cdf.query(sql=query_sql, s5=sample_df)

    dfres = res.to_pandas()
    dfres['interval'] = dfres['interval'] * 1e9
    dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['high_timestamp'] = dfres['high_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['low_timestamp'] = dfres['low_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['first_sample'] = dfres['first_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['last_sample'] = dfres['last_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    
    if (interval_bucket_type == 'WEEK' or (interval_bucket_type == 'MINUTE' and interval_bucket_size == 1440)):
        dfres['interval'] = dfres['interval'] + timedelta(days=1)

    # If > than Daily Interval then adjust datetime back by the original skew added to align Trading Day with Pandas Day boundary
    if (interval_bucket_type == 'WEEK' or (interval_bucket_type == 'MINUTE' and interval_bucket_size > 60)):
        if (interval_bucket_type == 'MINUTE' and interval_bucket_size > 60):
            dfres['interval'] = dfres['interval'] - timedelta(hours=hours_skew)
        dfres['high_timestamp'] = dfres['high_timestamp'] - timedelta(hours=hours_skew)
        dfres['low_timestamp'] = dfres['low_timestamp'] - timedelta(hours=hours_skew)
        dfres['first_sample'] = dfres['first_sample'] - timedelta(hours=hours_skew)
        dfres['last_sample'] = dfres['last_sample'] - timedelta(hours=hours_skew)

    # dfres = dfres.set_index('interval', drop=False)
    # print(dfres.head(10))
    # print(dfres.tail(1))
    return dfres

#### Experimental
    
def runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset, hours_skew=2):
    #Process samples to aggregate

    parquetSampleFile ='./data/oanda_data_pandas.parquet' 
    df = loadOptimisedSampleData(parquetSampleFile)

    if (interval_bucket_type == 'WEEK' or (interval_bucket_type == 'MINUTE' and interval_bucket_size > 60)):
        #Add 5 hours to the end of end and increment_end to align the shift to whole days - EST specific
        offset = 5
        start = start - timedelta(hours=offset)
        end = end - timedelta(hours=offset)

        # > H1 TF Specific skew added to align Trading Day with Pandas Day boundary
        df.index = df.index + timedelta(hours=hours_skew)

    last = False
    increment_end =  start + timedelta(hours=24*day_increment)

    while increment_end <= end:
        agg_df = aggregate_samples_to_interval(df, instrument, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, increment_end, tzOffset, hours_skew)

        #Workout the next increment in hours (not for Week (& Month?) Interval)
        if(interval_bucket_type == 'WEEK'):
            # Skip the Weekend...
            hrs = 24*(day_increment + 2)
        else:
             hrs = 24 * day_increment

        start =  start + timedelta(hours=hrs)
        increment_end =  start + timedelta(hours=hrs)

        if last:
            break
        if increment_end >= end:
            last = True
            increment_end = end

        parquetFile = storeIntermediateData(instrument, tf, agg_df)
        insertOHLCs(instrument, tf, parquetFile)

    outputFinalDataSet(instrument, tf)


#interval_bucket_type: MINUTE, WEEK, MONTH
def GenerateMinuteOHLC(instrument, start, end, minutes):
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = minutes
    interval_bucket_type = 'MINUTE'
    tf = f'M{minutes}'

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    print(f"Finished Minute={minutes} OHLC")

def GenerateHourlyOHLC(instrument, start, end):
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = 60
    interval_bucket_type = 'MINUTE'
    tf = 'H1'

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    print("Finished Hourly OHLC")

def Generate4HourlyOHLC(instrument, start, end, FXAnchor):
    # FXAnchor = True then 1st weekly H4 Candle starts at 17:00 Sun EST (same as Daily Skew)
    # FXAnchor = False then (Futures) 1st weekly H4 Candle starts at 18:00 Sun EST
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = 240
    interval_bucket_type = 'MINUTE'
    tf = 'H4'
    hours_skew = 2

    if not FXAnchor:
        hours_skew = 1

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset, hours_skew)
    print("Finished 4 Hourly OHLC")
    
def Generate6HourlyOHLC(instrument, start, end, FXAnchor):
    # FXAnchor = True then 1st weekly H4 Candle starts at 17:00 Sun EST (same as Daily Skew)
    # FXAnchor = False then (Futures) 1st weekly H4 Candle starts at 18:00 Sun EST
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = 360
    interval_bucket_type = 'MINUTE'
    tf = 'H6'
    hours_skew = 2

    if not FXAnchor:
        hours_skew = 1

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset, hours_skew)
    print("Finished 6 Hourly OHLC")

def GenerateDailyOHLC(instrument, start, end):
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = 1440
    interval_bucket_type = 'MINUTE'
    tf = 'D1'

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    print("Finished Daily OHLC")

def GenerateWeeklyOHLC(instrument, start, end):
    # Bucket by Weekly Intervals
    # Align data increment start to Week Boundary to avoid adding rows - maybe avoid this by ordering my sample count desc when outputting final OHLC to get the most complete interval?
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = 1
    interval_bucket_type = 'WEEK'
    tf = 'W1'

    #Align to Week Bounday (Monday=0)
    if start.weekday() > 0:
        start = start + timedelta(days= 7 - start.weekday())
        end = end + timedelta(days= 7 - start.weekday())

    intervalAggregateTerm = f"toDateTime(toStartOfWeek(s5.timestamp, 4, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    print("Finished Weekly OHLC")


