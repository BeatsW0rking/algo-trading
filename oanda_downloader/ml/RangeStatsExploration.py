#%% Imports
import math
import os
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import random
import seaborn as sns
import time
import json
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
import ta

import chdb #needs Linux / OSX
from chdb.session import Session
import chdb.dataframe as cdf
from pathlib import Path

#%%
pd.options.mode.copy_on_write = True
random.seed(10765)
baseDataPath = '../data/'
dbpath = '/tmp/aggregated_oanda_ranges'
# set_config(transform_output = "pandas")

#%% Load Data
def load_df_from_parquet(parquetFile):
    #Load optimised dataframe from parquet file
    start = time.time()
    dfFile = parquetFile
    df = pd.read_parquet(path=dfFile)
    end = time.time()
    print(f"Loaded Parquet Data:{parquetFile}, took:{end - start}")
    return df

def loadDataSet(instrument, tf):          
    dfFile = f"{baseDataPath}oanda_features_{instrument}_{tf}.parquet"
    return load_df_from_parquet(dfFile)

instrument = 'NAS100_USD' #'EUR_USD'
days = []
bins = [0, 1, 2, 3, 4, 5, 6, 7]
day_names = np.array(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])

## Weekly:
# df_weekly = loadDataSet(instrument, 'W1')
# df_weekly['high_day_of_week_trading'] = day_names[df_weekly['high_day_of_week_trading']]
# df_weekly['high_day_of_week_trading'] = pd.Categorical(df_weekly['high_day_of_week_trading'], categories=day_names)
# df_weekly['low_day_of_week_trading'] = day_names[df_weekly['low_day_of_week_trading']]
# df_weekly['low_day_of_week_trading'] = pd.Categorical(df_weekly['low_day_of_week_trading'], categories=day_names)


## Daily:
# df_daily = loadDataSet(instrument, 'D1')
# #TODO pull into Generation of PArquet Files.
# df_daily = df_daily.rename(columns={"high_proportion_of_day": "high_proportion_of_interval", "low_proportion_of_day": "low_proportion_of_interval"}) 

# ## 4 Hourly:
# df_4hourly = loadDataSet(instrument, 'H4')

## Hourly:
df_hourly = loadDataSet(instrument, 'H1')

# oddrows = df_hourly.query('low_day_of_week_trading >4') 
# # oddrows.head()
# oddrows.index
# skewed = df_hourly.loc[oddrows.index].index
# print('Found H1 TF Skewed Data')
# print(skewed)
# skewed_count = skewed.shape[0]
# df_hourly = df_hourly.drop(skewed)
# print(f'Dropped {skewed_count}')

df_hourly['high_day_of_week_trading'] = day_names[df_hourly['high_day_of_week_trading']]
df_hourly['high_day_of_week_trading'] = pd.Categorical(df_hourly['high_day_of_week_trading'], categories=day_names)
df_hourly['low_day_of_week_trading'] = day_names[df_hourly['low_day_of_week_trading']]
df_hourly['low_day_of_week_trading'] = pd.Categorical(df_hourly['low_day_of_week_trading'], categories=day_names)

# ## M15:
# df_m15 = loadDataSet(instrument, 'M15')

# ## M5:
df_m5 = loadDataSet(instrument, 'M5')

## M2:
df_m2 = loadDataSet(instrument, 'M2')

## M1:
df_m1 = loadDataSet(instrument, 'M1')

# df_m1.describe()

# oddrows = df_m1.query('low_day_of_week_trading >4') 
# # oddrows.head(1000)
# # oddrows.index
# # skewed = df_m1.loc[oddrows.index].index
# # print('Found H1 TF Skewed Data')
# # print(skewed)
# # skewed_count = skewed.shape[0]
# df_m1 = df_m1.drop(oddrows.index)
# # print(f'Dropped {skewed_count}')
# print(f'Dropped {oddrows.shape[0]}')
# df_m1.describe()
# oddrows.head()
# %% LTF SQL

df_h = df_hourly.copy(deep=True)
df_h.reset_index(names='interval', inplace=True)
df_m = df_m1.copy(deep=True)
df_m.reset_index(names='interval', inplace=True)



query_sql = f"""
    --select s.interval, s.open, s.high, s.low, s.close, s.open
    --[1] as h1_open,
    --[2] as h2_open
    --from  
    --(
     select 
       * 
     from 
        (
            select interval, high_timestamp, low_timestamp, h.open, h.high, h.low, h.close, h.day_of_week, hour_of_day, high_day_of_week_trading, high_minute_of_hour, interval_range, interval_return, ATR, bullish,
            m1.interval --, m1.open, m1.high, m1.low, m1.close, 
            --toMinute(m1.interval)
            from __hourly__ as h inner join __minutely__ as m1 on toYYYYMMDD(h.interval) = toYYYYMMDD(m1.interval) and hour(h.interval) = hour(m1.interval)
            where h.interval > makeDate(2023, 11, 11))
    -- )s
    group by all
    limit 10
    --PIVOT
    --(MAX(open) for rn in ([1],[2])) p
    ;
    """
#  interval as interval, open as dopen, high as high, low as low, close as close, h.open as open,
        #  row_number() over(partition by day(h.interval) order by h.interval) rn

res = cdf.query(sql=query_sql, minutely=df_m, hourly=df_h)

dfres = res.to_pandas()
dfres.head()
# %%
# df_m.head()
df_hourly.columns.values
# %%
def add_m1_to_h1_df(df_m1, df_hourly):
    df_h = df_hourly.copy(deep=True)
    df_h.reset_index(names='interval', inplace=True)
    df_m = df_m1.copy(deep=True)
    df_m.reset_index(names='interval', inplace=True)
    # df_m5x = df_m5.copy(deep=True)
    # df_m5x.reset_index(names='interval', inplace=True)

    query_sql = f"""
        select 
            sq.samples,
            sq.interval, sq.open, sq.high, sq.low, sq.close,
            max(sq.m0_interval) as m0_interval, max(sq.m0_open) as m0_open, max(sq.m0_high) as m0_high, max(sq.m0_low) as m0_low, max(sq.m0_close) as m0_close,
            max(sq.m0_high) - max(sq.m0_low) as m0_range,  max(sq.m0_close) - max(sq.m0_open) as m0_return,
            max(sq.m1_interval) as m1_interval, max(sq.m1_open) as m1_open, max(sq.m1_high) as m1_high, max(sq.m1_low) as m1_low, max(sq.m1_close) as m1_close,
            max(sq.m1_high) - max(sq.m1_low) as m1_range,  max(sq.m1_close) - max(sq.m1_open) as m1_return,
            max(sq.m2_interval) as m2_interval, max(sq.m2_open) as m2_open, max(sq.m2_high) as m2_high, max(sq.m2_low) as m2_low, max(sq.m2_close) as m2_close,
            max(sq.m2_high) - max(sq.m2_low) as m2_range,  max(sq.m2_close) - max(sq.m2_open) as m2_return,
            sq.day_of_week, sq.hour_of_day, 
            sq.high_minute_of_hour, sq.high_hour_of_day_trading, sq.high_day_of_week_trading, 
            sq.low_minute_of_hour, sq.low_hour_of_day_trading, sq.low_day_of_week_trading, 
            sq.interval_range, sq.interval_return, sq.ATR, sq.bullish
        from
            (select 
            h.interval, h.open, h.high, h.low, h.close, 
            h.day_of_week, 
            h.hour_of_day, 
            h.high_day_of_week_trading,
            h.high_hour_of_day_trading,
            h.high_minute_of_hour,
            h.low_day_of_week_trading,
            h.low_hour_of_day_trading,
            h.low_minute_of_hour, 
            h.interval_range, 
            h.interval_return, 
            h.ATR, 
            h.bullish,
            FIRST_VALUE(s5.interval) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) as m0_interval,
            FIRST_VALUE(s5.open) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m0_open,
            FIRST_VALUE(s5.high) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m0_high,
            FIRST_VALUE(s5.low)  OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m0_low,
            FIRST_VALUE(s5.close) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m0_close,
            NTH_VALUE(s5.interval, 2) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) as m1_interval,
            NTH_VALUE(s5.open, 2) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m1_open,
            NTH_VALUE(s5.high, 2) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m1_high,
            NTH_VALUE(s5.low, 2)  OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m1_low,
            NTH_VALUE(s5.close, 2) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m1_close,
            NTH_VALUE(s5.interval, 3) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) as m2_interval,
            NTH_VALUE(s5.open, 3) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m2_open,
            NTH_VALUE(s5.high, 3) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m2_high,
            NTH_VALUE(s5.low, 3)  OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m2_low,
            NTH_VALUE(s5.close, 3) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) m2_close,
            count(*) OVER (PARTITION BY h.interval) as samples 
            from __hourly__ as h inner join __minutely__ as s5 on toYYYYMMDD(h.interval) = toYYYYMMDD(s5.interval) and hour(h.interval) = hour(s5.interval)
            --where h.interval = makeDateTime(2024, 8, 27, 4, 0, 0) 
            order by h.interval
            ) as sq
        group by all
        order by sq.interval asc
        ;
        """


    test_sql = f"""
        select
            interval, open, high
        from  __minutely__ as s5
        
        --__hourly__ as h inner join __minutely__ as s5 on toYYYYMMDD(h.interval) = toYYYYMMDD(s5.interval) and hour(h.interval) = hour(s5.interval)
        --   where h.interval = makeDateTime(2024, 8, 27, 4, 0, 0) 
        where s5.interval >= makeDateTime(2024, 8, 27, 4, 0, 0) and  s5.interval < makeDateTime(2024, 8, 27, 5, 0, 0) 
            group by all
            order by s5.interval
    """

    # query_sql = f"""
    #     select sq.interval, sq.h_open, sq.h_close, sq.h_high, sq.open, sq.high, sq.low, sq.close, sq.high_timestamp, sq.low_timestamp, sq.samples as samples, sq.first_sample as first_sample, sq.last_sample as last_sample, sq.high_minute_of_hour 
    #     from
    #         (select 
    #         h.interval, high_timestamp, low_timestamp, h.open as h_open, h.high as h_high, h.low as h_low, h.close as h_close, h.day_of_week, hour_of_day, high_day_of_week_trading, high_minute_of_hour, interval_range, interval_return, ATR, bullish,
    #         FIRST_VALUE(s5.interval) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) as first_sample,
    #         FIRST_VALUE(s5.interval) OVER (PARTITION BY h.interval ORDER BY s5.interval desc) as last_sample,
    #         FIRST_VALUE(s5.open) OVER (PARTITION BY h.interval ORDER BY s5.interval asc) open,
    #         FIRST_VALUE(s5.high) OVER (PARTITION BY h.interval ORDER BY s5.high desc) high,
    #         FIRST_VALUE(s5.low)  OVER (PARTITION BY h.interval ORDER BY s5.low asc) low,
    #         FIRST_VALUE(s5.close) OVER (PARTITION BY h.interval ORDER BY s5.interval desc) close,
    #         FIRST_VALUE(s5.interval) OVER (PARTITION BY h.interval ORDER BY s5.high desc, s5.interval) high_timestamp,
    #         FIRST_VALUE(s5.interval) OVER (PARTITION BY h.interval ORDER BY s5.low asc, s5.interval) low_timestamp,
    #         count(*) OVER (PARTITION BY h.interval) as samples 
    #         from __hourly__ as h inner join __minutely__ as s5 on toYYYYMMDD(h.interval) = toYYYYMMDD(s5.interval) and hour(h.interval) = hour(s5.interval)
    #         where h.interval >= makeDate(2023, 11, 11) 
    #         order by h.interval
    #         ) as sq
    #     group by sq.interval, sq.h_open, sq.h_high, sq.h_close, sq.open, sq.high , sq.low, sq.close, sq.high_timestamp, sq.low_timestamp, sq.samples, sq.first_sample, sq.last_sample, sq.high_minute_of_hour
    #     order by sq.interval desc
    #     ;
    #     """
    res = cdf.query(sql=query_sql, minutely=df_m1, hourly=df_h)

    # res = cdf.query(sql=query_sql, minutely=df_m1, hourly=df_h, m5=df_m5x)

    dfres = res.to_pandas()
    # dfres.head(1000)
    # print(dfres.to_string())
    return dfres

def add_features(df):
    df[f'failed_exp_higher'] = (df.high > df.high.shift(1)) & (df.close < df.high.shift(1))
    df[f'failed_exp_lower'] = (df.low < df.low.shift(1)) & (df.close > df.low.shift(1))
    df['prior_h1_high'] = df.high.shift(1)
    df['prior_h1_low'] = df.low.shift(1)
    return df
    
    
df_h1_m1 = add_m1_to_h1_df(df_m1, df_hourly)
df_h1_m1 = add_features(df_h1_m1)


#%% Aggregation Functions:
def clearOHLCTable():
    db = Session(path=dbpath)
    
    db.query("truncate TABLE IF EXISTS quant.ohlc_agg")
    db.close()
    
def loadOptimisedSampleData(parquetFile):
    #Load optimised dataframe from parquet file
    start = time.time()
    dfFile = parquetFile #'./data/oanda_data_pandas.parquet'
    df = pd.read_parquet(path=dfFile)
    end = time.time()
    print("Loaded Optimised Sample Data:", end - start)
    return df

def insertOHLCs(instrument, tf, parquetFile):

    data = f"file('{parquetFile}', Parquet)"
    db = Session(path=dbpath)
    
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
    dfFile = f"{baseDataPath}oanda_data_intermediate_{instrument}_{tf}.parquet"
    bars.to_parquet(path=dfFile, index=True)
    end = time.time()
    # print(end - start)
    return dfFile

def outputFinalDataSet(instrument, tf):
    db = Session(path=dbpath)
    
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
    dfFile = f'{baseDataPath}oanda_{instrument}_{tf}_range.parquet'
    dfres.to_parquet(path=dfFile, index=True)
    end = time.time()
    print(end - start)
    dfres = None

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
#interval_bucket_type: MINUTE, WEEK, MONTH

def runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset, hours_skew=2):
    #Process samples to aggregate

    parquetSampleFile =f'{baseDataPath}oanda_data_pandas.parquet' 
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
    
def GenerateMinuteOHLC(instrument, start, end, minutes):
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = minutes
    interval_bucket_type = 'MINUTE'
    tf = f'M{minutes}'

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"

    runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    print(f"Finished Minute={minutes} OHLC")
#%% - See what the latest date is in the DataFiles:
# tf= 'H1'
# datafile = f"{baseDataPath}oanda_{instrument}_{tf}.parquet"


# parquetSampleFile = f"{baseDataPath}oanda_data_pandas.parquet" 
# df_tmp = load_df_from_parquet(parquetSampleFile)
# df_tmp.query("instrument == 'NAS100_USD'").head()
db = Session(path="/tmp/oanda_data")
query_sql = f"""
    select instrument, min(timestamp) as first_sample, max(timestamp) as last_timestamp, count(*) as samples 
    --select *
    from quant.ohlc
    where instrument = 'NAS100_USD'
    group by instrument 
    limit 10
        """
res = db.query(query_sql, 'Dataframe') #, minutely=df_m, hourly=df_h)

dfrest = res
dfrest.head()

#%% Scratch Funcs

def aggregate_samples_to_range(sample_df, instrument, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, tzOffset, hours_skew=2):
    print(f'Calling aggregate_samples_to_interval with start: {start}, end: {end}, interval_bucket_size: {interval_bucket_size}, interval_bucket_type: {interval_bucket_type}, tzOffset: {tzOffset}')
    query_sql = f"""
    select 
        sq.interval as interval,
        {interval_bucket_size} as interval_size_minutes,
        max(sq.open) as open, max(sq.high) as high, max(sq.low) as low, max(sq.close) as close, 
        max(sq.high_timestamp) as high_timestamp, 
        max(sq.low_timestamp) as low_timestamp,
        COALESCE(
            ROUND(
                    (
                        (toDateTime(max(sq.high_timestamp), '{tzOffset}') - sq.interval)
                        / 
                        ({interval_bucket_size}*60)
                    )
                ,2)
        ) as high_proportion_of_interval,
        COALESCE(
            ROUND(
                    (
                        (toDateTime(max(sq.low_timestamp), '{tzOffset}') - sq.interval)
                        / 
                        ({interval_bucket_size}*60)
                    )
                ,2)
        ) as low_proportion_of_interval,
        max(sq.samples) as samples, 
        max(sq.first_sample) as first_sample, max(sq.last_sample) as last_sample 
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

def GenerateRangeOHLC(instrument, start, end, minutes):
    tzOffset = 'EST'
    day_increment = 5
    interval_bucket_size = minutes
    interval_bucket_type = 'MINUTE'
    tf = f'M{minutes}'

    intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type}, '{tzOffset}')) as interval"
    # intervalAggregateTerm = f"toDateTime(toStartOfInterval(s5.timestamp, INTERVAL {interval_bucket_size} {interval_bucket_type})) as interval"

    # runFullAggregationPipeline(day_increment, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, instrument, tf, tzOffset)
    parquetSampleFile =f'{baseDataPath}oanda_data_pandas.parquet' 
    df = loadOptimisedSampleData(parquetSampleFile)
    hours_skew=2
    agg_df = aggregate_samples_to_range(df, instrument, interval_bucket_size, interval_bucket_type, intervalAggregateTerm, start, end, tzOffset, hours_skew)

    print(f"Finished GenerateRangeOHLC={minutes} OHLC")
    
    return agg_df

def SelectRangefromUniverseHourly(df_ranges, rangeStartMinute):
    # df_range = df_range.query(f"interval >= '{rangeStart}' and interval < '{rangeEnd}'")
    
    query_sql = f"""
    select 
        sq.interval as interval,
        sq.interval_size_minutes as interval_size_minutes, 
        sq.open as open, sq.high as high, sq.low as low, sq.close as close, 
        sq.high_timestamp as high_timestamp, 
        sq.low_timestamp as low_timestamp,
        sq.high_proportion_of_interval as high_proportion_of_interval,
        sq.low_proportion_of_interval as low_proportion_of_interval,
        sq.samples as samples, 
        sq.first_sample as first_sample, sq.last_sample as last_sample 
    from __s5__ as sq
        where toMinute(sq.interval) = {rangeStartMinute}
    order by sq.interval asc
    ;
    """
    res = cdf.query(sql=query_sql, s5=df_ranges)
    tzOffset = 'EST'
    
    dfres = res.to_pandas()
    # dfres['interval'] = dfres['interval'] * 1e9
    dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['high_timestamp'] = dfres['high_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['low_timestamp'] = dfres['low_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['first_sample'] = dfres['first_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['last_sample'] = dfres['last_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    
    return dfres

def SelectRangefromUniverseDaily(df_ranges, rangeStartHour, rangeStartMinute):
    # df_range = df_range.query(f"interval >= '{rangeStart}' and interval < '{rangeEnd}'")
    tzOffset = 'EST'
    query_sql = f"""
    select 
        sq.interval as interval, 
        sq.interval_size_minutes as interval_size_minutes,
        sq.open as open, sq.high as high, sq.low as low, sq.close as close, 
        sq.high_timestamp as high_timestamp, 
        sq.low_timestamp as low_timestamp,
        sq.high_proportion_of_interval as high_proportion_of_interval,
        sq.low_proportion_of_interval as low_proportion_of_interval,
        sq.samples as samples, 
        sq.first_sample as first_sample, sq.last_sample as last_sample 
    from __s5__ as sq
        where toHour(toDateTime(sq.interval, '{tzOffset}')) = {rangeStartHour} and toMinute(sq.interval) = {rangeStartMinute}
    order by sq.interval asc
    ;
    """
    res = cdf.query(sql=query_sql, s5=df_ranges)
    
    
    dfres = res.to_pandas()
    # dfres['interval'] = dfres['interval'] * 1e9
    dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['high_timestamp'] = dfres['high_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['low_timestamp'] = dfres['low_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['first_sample'] = dfres['first_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    dfres['last_sample'] = dfres['last_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    
    return dfres


class Range:
    def __init__(self, interval, interval_size_minutes, open, high, low, close, high_timestamp, low_timestamp, high_proportion_of_interval, low_proportion_of_interval, samples, first_sample, last_sample):
        self.interval = interval
        self.interval_size_minutes = interval_size_minutes
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.high_timestamp = high_timestamp
        self.low_timestamp = low_timestamp
        self.high_proportion_of_interval = high_proportion_of_interval
        self.low_proportion_of_interval = low_proportion_of_interval
        self.samples = samples
        self.first_sample = first_sample
        self.last_sample = last_sample
        self.activated_at = None
        self.activated_at_pc = None
        self.activated_direction = None
        self.max_1st_displacement = 0
        self.max_1st_displacement_pc = None
        self.max_1st_displacement_at = None
        self.max_1st_displacement_at_pc = None
        self.max_activated_displacement = 0 #How far price moved form the range in the inital activation direction after the intial displacement
        self.max_activated_displacement_pc = None
        self.max_activated_displacement_at = None
        self.max_activated_displacement_at_pc = None
        self.return_to_range_qtl_at = None
        self.return_to_range_qtl_at_pc = None
        self.return_to_range_open_at = None
        self.return_to_range_open_at_pc = None
        self.return_to_range_open_prior_beyond_max_1st_price_displacement = None
        self.return_to_range_eq_at = None
        self.return_to_range_eq_at_pc = None
        self.return_to_range_eq_prior_beyond_max_1st_price_displacement = None
        self.return_to_range_extreme_at = None
        self.return_to_range_extreme_at_pc = None
        self.return_to_range_extreme_prior_beyond_max_1st_price_displacement = None
        self.max_displacement_range_extreme = 0
        self.max_displacement_range_extreme_pc = None
        self.max_displacement_range_extreme_at = None
        self.max_displacement_range_extreme_at_pc = None

    def __repr__(self):
        return f"Range(interval={self.interval}, open={self.open}, high={self.high}, low={self.low}, close={self.close})"
# db = Session(path=dbpath)
# tf='M1'
# instrument = 'NAS100_USD'    
# query = f"select * from quant.ohlc_agg where instrument='{instrument}' and tf='{tf}' order by interval"
# dfres = db.query(query, 'dataframe')
# dfres.head()

#%% Generate Range Universe
start = datetime(2024, 1, 1) #datetime(2024, 8, 31) 
end = datetime(2024, 1, 8) #datetime(2024, 8, 31)
instrument = 'NAS100_USD'
minutes = 15
# chdb.close()
clearOHLCTable()
df_range_universe = GenerateRangeOHLC(instrument, start, end, minutes)

parquetSampleFile =f'{baseDataPath}oanda_data_pandas.parquet' 
sample_df = loadOptimisedSampleData(parquetSampleFile)

#%% Select Ranges of Interest
rangeStartMinute = 0
rangeStartHour = 10
# df_ranges = SelectRangefromUniverseHourly(df_range_universe, rangeStartMinute) 
df_ranges = SelectRangefromUniverseDaily(df_range_universe, rangeStartHour, rangeStartMinute) 
df_ranges.head()
# Range Size 
# Range Start, Range End (Range Start + Range Size)

# 1. Time since Range Formed that it was broken (% of range time)
#  If Price <> Range High or Low then Range Broken - record the time and % of Range and that range has been broken
# 2. Direction of Break (Long/Short)
# 3. Maximum Price Displacement from Range before returning to Range (% of Range H/L) - Manipulation
# 4. Time of Maximum Displacement (% of Range Time)
# 5. Time Price returned to the Range (% of Range Time)
# 6. Time Price returned to the Price at the start of the Range (Open) (% of Range)
# 7. Does it return to the Price at the start of the Range (Open) before Displacing beyond 1st Max Displacement again
# 8. Time Price returned to the EQ of the Range (% of Range)
# 9. Does it get to EQ of the range before Displacing beyond 1st Max Displacement again
# 10. Time Price returned to the Other side of the Range (% of Range)
# 11. Does it get to the other side of the range before Displacing beyond 1st Max Displacement again
# 12. Maximum Price Displacement from Other side of Range before returning to Range (% of Range H/L)
# 13. Time of Maximum Price Displacement from Other side of Range (% of Range Time)
computed_columns = [
    'activated_at', 
    'activated_at_pc', 
    'activated_direction',
    'max_1st_displacement',
    'max_1st_displacement_pc',
    'max_1st_displacement_at',
    'max_1st_displacement_at_pc',
    'max_activated_displacement',
    'max_activated_displacement_pc',
    'max_activated_displacement_at',
    'max_activated_displacement_at_pc',
    'return_to_range_qtl_at',
    'return_to_range_qtl_at_pc',
    'return_to_range_open_at',
    'return_to_range_open_at_pc',
    'return_to_range_open_prior_beyond_max_1st_price_displacement',
    'return_to_range_eq_at',
    'return_to_range_eq_at_pc',
    'return_to_range_eq_prior_beyond_max_1st_price_displacement',
    'return_to_range_extreme_at',
    'return_to_range_extreme_at_pc',
    'return_to_range_extreme_prior_beyond_max_1st_price_displacement',
    'max_displacement_range_extreme',
    'max_displacement_range_extreme_pc',
    'max_displacement_range_extreme_at',
    'max_displacement_range_extreme_at_pc',
    ]
# df_ranges = df_ranges.assign(computed_columns)
df_ranges = df_ranges.reindex(columns=df_ranges.columns.tolist() + computed_columns)

def GetS5DataFromRangeEnd(sample_df, instrument, start, end, tzOffset):
    query_sql = f"""
    select 
        s5.timestamp as interval,
        s5.open as open, s5.high as high, s5.low as low, s5.close as close
        from __s5__ as s5
        where s5.instrument='{instrument}' 
        and s5.timestamp >= toDateTime('{start}', '{tzOffset}') 
        and s5.timestamp < toDateTime('{end}', '{tzOffset}')
        order by s5.timestamp asc
    ;
    """
    res = cdf.query(sql=query_sql, s5=sample_df)

    dfres = res.to_pandas()
    # dfres['interval'] = dfres['interval'] * 1e9
    dfres['interval'] = dfres['interval'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
    return dfres

### Can be used to Evaluate Maximum Favourable Excursion from specific Ranges === Candles - e.g. test 02:00 H4 Candle PSP Expansion...
def ProcessRange(r, df_post_range_data):
    # print(f'Processing: {r.interval} Open: {r.open} High % of Interval: {r.high_proportion_of_interval}')
    
    for index, row in df_post_range_data.iterrows():
        # if index < 4:
        #     print(f'Processing: {index} - {row["interval"]} Open: {row["open"]} High: {row["high"]} Low: {row["low"]} Close: {row["close"]}')
        # Activate Range = Trade above the range high or belwo the range low
        if row['high'] > r.high and r.activated_at is None:
            r.activated_at = row['interval']
            r.activated_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
            r.activated_direction = 'Long'
        if row['low'] < r.low and r.activated_at is None:
            r.activated_at = row['interval']
            r.activated_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
            r.activated_direction = 'Short'
            
        # 1st Displacement (Activation) from Range High/Low
        if r.activated_direction == 'Long' and r.return_to_range_qtl_at is None:
            r.max_1st_displacement = max(r.max_1st_displacement, row['high'] - r.high)
            r.max_1st_displacement_pc = r.max_1st_displacement / (r.high - r.low)
            r.max_1st_displacement_at = row['interval']
            r.max_1st_displacement_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short'and r.return_to_range_qtl_at is None:
            r.max_1st_displacement = max(r.max_1st_displacement, r.low - row['low'])
            r.max_1st_displacement_pc = r.max_1st_displacement / (r.high - r.low)
            r.max_1st_displacement_at = row['interval']
            r.max_1st_displacement_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
            
        # Max displacement from the Range High/Low after activation
        if r.activated_direction == 'Long':
            r.max_activated_displacement = max(r.max_activated_displacement, row['high'] - r.high)
            r.max_activated_displacement_pc = r.max_activated_displacement / (r.high - r.low)
            r.max_activated_displacement_at = row['interval']
            r.max_activated_displacement_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short':
            r.max_activated_displacement = max(r.max_activated_displacement, r.low - row['low'])
            r.max_activated_displacement_pc = r.max_activated_displacement / (r.high - r.low)
            r.max_activated_displacement_at = row['interval']
            r.max_activated_displacement_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))

        # Return to the Range (close belwo 1st Qtle) after Max Displacement ======= NEED appropriate hyterisis logic here to enable an expansion to get underway... Time?
        if r.activated_direction == 'Long' and r.return_to_range_qtl_at is None and row['close'] < (r.high - (r.high - r.low) / 4):
            r.return_to_range_qtl_at = row['interval']
            r.return_to_range_qtl_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short' and r.return_to_range_qtl_at is None and row['close'] > (r.low + (r.high - r.low) / 4):
            r.return_to_range_qtl_at = row['interval']
            r.return_to_range_qtl_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        
        # Trade back to the Range Open
        if r.activated_direction == 'Long' and r.return_to_range_open_at is None and row['low'] < r.open:
            r.return_to_range_open_at = row['interval']
            r.return_to_range_open_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short' and r.return_to_range_open_at is None and row['high'] > r.open:
            r.return_to_range_open_at = row['interval']
            r.return_to_range_open_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
           
        # Return to the Range Open before Displacing beyond 1st Max Displacement again
        if r.activated_direction == 'Long' and r.return_to_range_open_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_open_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_open_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_open_prior_beyond_max_1st_price_displacement = False
        if r.activated_direction == 'Short' and r.return_to_range_open_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_open_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_open_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_open_prior_beyond_max_1st_price_displacement = False
        # EQ
        if r.activated_direction == 'Long' and r.return_to_range_eq_at is None and row['low'] < (r.high - (r.high - r.low) / 2):
            r.return_to_range_eq_at = row['interval']
            r.return_to_range_eq_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short' and r.return_to_range_eq_at is None and row['high'] > (r.low + (r.high - r.low) / 2):
            r.return_to_range_eq_at = row['interval']
            r.return_to_range_eq_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
            
        # Return to the Range EQ before Displacing beyond 1st Max Displacement again
        if r.activated_direction == 'Long' and r.return_to_range_eq_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_eq_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_eq_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_eq_prior_beyond_max_1st_price_displacement = False
        if r.activated_direction == 'Short' and r.return_to_range_eq_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_eq_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_eq_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_eq_prior_beyond_max_1st_price_displacement = False
            
        # Extreme
        if r.activated_direction == 'Long' and r.return_to_range_extreme_at is None and row['low'] < r.low:
            r.return_to_range_extreme_at = row['interval']
            r.return_to_range_extreme_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short' and r.return_to_range_extreme_at is None and row['high'] > r.high:
            r.return_to_range_extreme_at = row['interval']
            r.return_to_range_extreme_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
            
        # Return to the Range Extreme before Displacing beyond 1st Max Displacement again   
        if r.activated_direction == 'Long' and r.return_to_range_extreme_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_extreme_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_extreme_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_extreme_prior_beyond_max_1st_price_displacement = False
        if r.activated_direction == 'Short' and r.return_to_range_extreme_prior_beyond_max_1st_price_displacement is None and r.max_activated_displacement_at is not None and r.return_to_range_extreme_at is not None:
            if r.max_activated_displacement < r.max_1st_displacement:
                r.return_to_range_extreme_prior_beyond_max_1st_price_displacement = True
            else:
                r.return_to_range_extreme_prior_beyond_max_1st_price_displacement = False
                
        # Extreme Displacement
        if r.activated_direction == 'Long' and r.max_displacement_range_extreme_at is None:
            r.max_displacement_range_extreme = max(r.max_displacement_range_extreme, r.low - row['low'])
            r.max_displacement_range_extreme_pc = r.max_displacement_range_extreme / (r.high - r.low)
            r.max_displacement_range_extreme_at = row['interval']
            r.max_displacement_range_extreme_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        if r.activated_direction == 'Short' and r.max_displacement_range_extreme_at is None:
            r.max_displacement_range_extreme = max(r.max_displacement_range_extreme,  row['high'] - r.high)
            r.max_displacement_range_extreme_pc = r.max_displacement_range_extreme / (r.high - r.low)
            r.max_displacement_range_extreme_at = row['interval']
            r.max_displacement_range_extreme_at_pc = ((row['interval'] - (r.interval + timedelta(minutes=r.interval_size_minutes))) / timedelta(minutes=r.interval_size_minutes))
        
    print(r)
    return r


instrument = 'NAS100_USD'
# df_ranges.head()
for index, row in df_ranges.iterrows():
    # print(f'Processing: {index} - {row["interval"]} Open: {row["open"]} High % of Interval: {row["high_proportion_of_interval"]}')
    r = Range(row['interval'], row['interval_size_minutes'], row['open'], row['high'], row['low'], row['close'], row['high_timestamp'], row['low_timestamp'], row['high_proportion_of_interval'], row['low_proportion_of_interval'], row['samples'], row['first_sample'], row['last_sample'])
    
    #Need to get Date Time into UTC then convert back to EST in the SQL,.... argggh
    ts = pd.Timestamp(r.interval)
    # print(ts)
    # ts = ts.tz_convert('UTC')
    # print(ts)
    ts = ts.tz_localize(tz=None)
    # print(ts)
    tsEnd = ts + timedelta(days=10)
    # print(tsEnd)
    df_post_range_data = GetS5DataFromRangeEnd(sample_df, instrument, ts, tsEnd, 'EST')
    # df_post_range_data.head()
    r = ProcessRange(r, df_post_range_data)
    print(f'Range: {r.interval} \n activated_at: {r.activated_at} \n activated_direction: {r.activated_direction} \n activated_at_pc: {r.activated_at_pc}\n',
          f'max_1st_displacement {r.max_1st_displacement} \n max_1st_displacement_pc: {r.max_1st_displacement_pc} \n max_1st_displacement_at: {r.max_1st_displacement_at}\n max_1st_displacement_at_pc: {r.max_1st_displacement_at_pc}\n',
          f'max_activated_displacement {r.max_activated_displacement} \n max_activated_displacement_pc: {r.max_activated_displacement_pc} \n max_activated_displacement_at: {r.max_activated_displacement_at}\n max_activated_displacement_at_pc: {r.max_activated_displacement_at_pc}\n',
          f'return_to_range_qtl_at: {r.return_to_range_qtl_at} \n return_to_range_qtl_at_pc: {r.return_to_range_qtl_at_pc}\n',
          f'return_to_range_open_at: {r.return_to_range_open_at} \n return_to_range_open_at_pc: {r.return_to_range_open_at_pc}\n',
          f'return_to_range_open_prior_beyond_max_1st_price_displacement: {r.return_to_range_open_prior_beyond_max_1st_price_displacement}\n',
          f'return_to_range_eq_at: {r.return_to_range_eq_at} \n return_to_range_eq_at_pc: {r.return_to_range_eq_at_pc}\n',
          f'return_to_range_eq_prior_beyond_max_1st_price_displacement: {r.return_to_range_eq_prior_beyond_max_1st_price_displacement}\n',
          f'return_to_range_extreme_at: {r.return_to_range_extreme_at} \n return_to_range_extreme_at_pc: {r.return_to_range_extreme_at_pc}\n',
          f'return_to_range_extreme_prior_beyond_max_1st_price_displacement: {r.return_to_range_extreme_prior_beyond_max_1st_price_displacement}\n',
          f'max_displacement_range_extreme: {r.max_displacement_range_extreme} \n max_displacement_range_extreme_pc: {r.max_displacement_range_extreme_pc}\n',
          f'max_displacement_range_extreme_at: {r.max_displacement_range_extreme_at} \n max_displacement_range_extreme_at_pc: {r.max_displacement_range_extreme_at_pc}\n',
          f'interval: {r.interval} \n open: {r.open} \n high: {r.high} \n low: {r.low} \n close: {r.close}\n',
          )
    # Insert the newly computed fields of Range r into the df_ranges dataframe
    df_ranges.at[index, 'activated_at'] = r.activated_at
    df_ranges.at[index, 'activated_at_pc'] = r.activated_at_pc
    df_ranges.at[index, 'activated_direction'] = r.activated_direction
    df_ranges.at[index, 'max_1st_displacement'] = r.max_1st_displacement
    df_ranges.at[index, 'max_1st_displacement_pc'] = r.max_1st_displacement_pc
    df_ranges.at[index, 'max_1st_displacement_at'] = r.max_1st_displacement_at
    df_ranges.at[index, 'max_1st_displacement_at_pc'] = r.max_1st_displacement_at_pc
    df_ranges.at[index, 'max_activated_displacement'] = r.max_activated_displacement
    df_ranges.at[index, 'max_activated_displacement_pc'] = r.max_activated_displacement_pc
    df_ranges.at[index, 'max_activated_displacement_at'] = r.max_activated_displacement_at
    df_ranges.at[index, 'max_activated_displacement_at_pc'] = r.max_activated_displacement_at_pc
    df_ranges.at[index, 'return_to_range_qtl_at'] = r.return_to_range_qtl_at
    df_ranges.at[index, 'return_to_range_qtl_at_pc'] = r.return_to_range_qtl_at_pc
    df_ranges.at[index, 'return_to_range_open_at'] = r.return_to_range_open_at
    df_ranges.at[index, 'return_to_range_open_at_pc'] = r.return_to_range_open_at_pc
    df_ranges.at[index, 'return_to_range_open_prior_beyond_max_1st_price_displacement'] = r.return_to_range_open_prior_beyond_max_1st_price_displacement
    df_ranges.at[index, 'return_to_range_eq_at'] = r.return_to_range_eq_at
    df_ranges.at[index, 'return_to_range_eq_at_pc'] = r.return_to_range_eq_at_pc
    df_ranges.at[index, 'return_to_range_eq_prior_beyond_max_1st_price_displacement'] = r.return_to_range_eq_prior_beyond_max_1st_price_displacement
    df_ranges.at[index, 'return_to_range_extreme_at'] = r.return_to_range_extreme_at
    df_ranges.at[index, 'return_to_range_extreme_at_pc'] = r.return_to_range_extreme_at_pc
    df_ranges.at[index, 'return_to_range_extreme_prior_beyond_max_1st_price_displacement'] = r.return_to_range_extreme_prior_beyond_max_1st_price_displacement
    df_ranges.at[index, 'max_displacement_range_extreme'] = r.max_displacement_range_extreme
    df_ranges.at[index, 'max_displacement_range_extreme_pc'] = r.max_displacement_range_extreme_pc
    df_ranges.at[index, 'max_displacement_range_extreme_at'] = r.max_displacement_range_extreme_at
    df_ranges.at[index, 'max_displacement_range_extreme_at_pc'] = r.max_displacement_range_extreme_at_pc
    
print(df_ranges.head(10))


    
            

# %% Execution:
start = datetime(2024, 1, 1) #datetime(2024, 8, 31) 
end = datetime(2024, 1, 8) #datetime(2024, 8, 31)
instrument = 'NAS100_USD'
minutes = 1
clearOHLCTable()
GenerateMinuteOHLC(instrument, start, end, minutes)
# 2024-08-26 23:00 - last Hour 
# Look at https://clickhouse.com/docs/sql-reference/window-functions/lagInFrame
# %%
start = datetime(2024, 1, 1, 10)
ts = pd.Timestamp(start)
print(ts)
ts = ts.tz_localize('UTC').tz_convert('EST')
print(ts)
ts = ts.tz_convert('UTC')
print(ts)
ts = ts.tz_localize(tz=None)
print(ts)
# %%
