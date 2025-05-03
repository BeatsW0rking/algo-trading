import calendar
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo
import pandas as pd
import ta
import random

random.seed(10765)
pd.options.mode.copy_on_write = True
# pd.options.mode.copy_on_write = False
df = None
baseDataPath = './data/'

def load_df_from_parquet(parquetFile):
    #Load optimised dataframe from parquet file
    start = time.time()
    dfFile = parquetFile
    df = pd.read_parquet(path=dfFile)
    end = time.time()
    print(f"Loaded Parquet Data:{parquetFile}, took:{end - start}")
    return df

def week_of_month(tgtdate):

    days_this_month = calendar.mdays[tgtdate.month]
    for i in range(1, days_this_month):
        d = datetime(tgtdate.year, tgtdate.month, i, tzinfo=ZoneInfo('EST'))
        if d.day - d.weekday() > 0:
            startdate = d
            break
    # now we can use the floor division 7 appraoch
    return (tgtdate - startdate).days //7 + 1

def loadIntervalDataframe(instrument, tf):
    # Load Data from Parquet:
    #     instrument = 'EUR_USD'
    #     tf = 'W1'
    tzOffset = 'EST'
    datafile = f"{baseDataPath}oanda_{instrument}_{tf}.parquet"
    df = load_df_from_parquet(datafile)
    
    if tf in ['W1', 'D1']:
        df.index = pd.to_datetime(df.index, utc=True)
    else:
        df.index = df.index.astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset))) #sorts out Trading Day in EST time.
        df['high_timestamp'] = df['high_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
        df['low_timestamp'] = df['low_timestamp'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
        df['first_sample'] = df['first_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))
        df['last_sample'] = df['last_sample'].astype(pd.DatetimeTZDtype(tz=ZoneInfo(tzOffset)))

    # Data Clean Up - need to push back into Parquet generation:
    # For some reason The Last Week in Oct starts on a Sunday instead of a Monday
    # Select all Weeks which are starting on a Sunday and add on day to the index....

    if tf == 'W1':
        oddrows = df['tf'] = 'W1' and df.index.dayofweek >4 #| (df.tf == 'D1' & df.index.dayofweek >4)
            # df.loc[oddrows].index = df.loc[oddrows].index + timedelta(days=1)

        skewed = df.loc[oddrows].index
        [df.rename(index={x: x + timedelta(days=1)},inplace=True) for x in skewed]
    
    if tf == 'D1':
        oddrows = df['tf'] = 'D1' and df.index.dayofweek >4 
            # df.loc[oddrows].index = df.loc[oddrows].index + timedelta(days=1)

        skewed = df.loc[oddrows].index
        print('Found D1 TF Skewed Data')
        print(skewed)
        skewed_count = skewed.shape[0]
        df = df.drop(skewed)
        print(f'Dropped {skewed_count}')
        # oddrowsck = df['tf'] = 'W1' and df.index.dayofweek >5
        # df.loc[oddrows].head(100)
    # print(df.head(10))    
    return df

# Work out the Proportion of the Interval the Highs and Lows occured at:
def weekHighProportionRow(row):
    grain = timedelta(hours=120)
    interval = pd.to_datetime(row.name, utc=True)
    interval = datetime(interval.year, interval.month, interval.day, 17,tzinfo=ZoneInfo('EST')) - timedelta(days=1)
    p = intervalProportion(grain, interval, row.high_timestamp)
    return p

def weekLowProportionRow(row):
    grain = timedelta(hours=120)
    interval = pd.to_datetime(row.name, utc=True)
    interval = datetime(interval.year, interval.month, interval.day, 17,tzinfo=ZoneInfo('EST')) - timedelta(days=1)
    p = intervalProportion(grain, interval, row.low_timestamp)
    return p

def dayHighProportionRow(row):
    grain = timedelta(hours=24)
    interval = pd.to_datetime(row.name, utc=True)
    interval = datetime(interval.year, interval.month, interval.day, 17,tzinfo=ZoneInfo('EST')) - timedelta(days=1)
    p = intervalProportion(grain, interval, row.high_timestamp)
    # print(f'row:{row.name}, interval:{interval}, p:{p}, hights:{row.high_timestamp}')
    return p

def dayLowProportionRow(row):
    grain = timedelta(hours=24)
    interval = pd.to_datetime(row.name, utc=True)
    interval = datetime(interval.year, interval.month, interval.day, 17,tzinfo=ZoneInfo('EST')) - timedelta(days=1)
    p = intervalProportion(grain, interval, row.low_timestamp)
    return p

# Below Daily Intevals
def intervalHighProportionRow(row, minutes): 
    grain = timedelta(minutes=minutes)
#     interval = row.name.astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST'))) #pd.to_datetime(row.name) #, utc=True)
    interval = row.name
    interval = datetime(interval.year, interval.month, interval.day, interval.hour, interval.minute, interval.second ,tzinfo=ZoneInfo('EST'))
    p = intervalProportion(grain, interval, row.high_timestamp)
    return p

def intervalLowProportionRow(row, minutes):
    grain = timedelta(minutes=minutes)
#     interval = pd.to_datetime(row.name) #, utc=True)
#     interval = row.name.astype(pd.DatetimeTZDtype(tz=ZoneInfo('EST')))
    interval = row.name
    interval = datetime(interval.year, interval.month, interval.day, interval.hour, interval.minute, interval.second ,tzinfo=ZoneInfo('EST'))
    p = intervalProportion(grain, interval, row.low_timestamp)
    return p

def intervalProportion(grain, interval, high_low_timestamp):
    high_low_datetime = pd.to_datetime(high_low_timestamp)
    start = interval
    segment_passed = high_low_datetime - start
    proportion = segment_passed / grain
#     print(f'interval: {interval}, high_low_datetime: {high_low_datetime}, segment_passed: {segment_passed}')
    return proportion


# Main Feature Engineering
def featureEng(df, tf_minutes):
    #Interval / Index
    dt_trading = df.index.to_series()
    df['year'] = df.index.year
    df['quarter_of_year'] = df.index.quarter
    df['month_of_year'] = df.index.month
    df['week_of_year'] = df.index.isocalendar().week
    df['week_of_month'] = df.apply(lambda row: week_of_month(row.name), axis=1)
    df['day_of_year'] = df.index.dayofyear
    df['day_of_month'] = df.index.day
    df['day_of_week'] = df.index.dayofweek
    df['hour_of_day'] = df.index.hour
    df['minute_of_hour'] = df.index.minute
    df['minute_of_day'] = (df.index.hour * 60) + df.index.minute
    df['second_of_minute'] = df.index.second
    df['day_of_week_trading'] = dt_trading.apply(lambda row: (row + timedelta(hours=7)).dayofweek)
    df['hour_of_day_trading'] =  dt_trading.apply(lambda row:  (row + timedelta(hours=7)).hour)
    df['minute_of_day_trading'] =  dt_trading.apply(lambda row: ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60)  
    df['minute_of_week_trading'] =  dt_trading.apply(lambda row: ((row + timedelta(hours=7)).dayofweek*24) + ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60) 
    if tf_minutes >= 1440: df.index = df.index.date

    # High Time Stamp
    high_ts = pd.to_datetime(df.high_timestamp)
    df['high_year'] = high_ts.dt.year
    df['high_quarter_of_year'] = high_ts.dt.quarter
    df['high_month_of_year'] = high_ts.dt.month
    df['high_week_of_year'] = high_ts.dt.isocalendar().week
    df['high_week_of_month'] = high_ts.apply(week_of_month)
    df['high_day_of_year'] = high_ts.dt.dayofyear
    df['high_day_of_month'] = high_ts.dt.day
#     df['high_day_of_week'] = high_ts.dt.dayofweek 
#     df['high_day_of_week_sun_0'] = high_ts.apply(lambda row: (row.dayofweek+ 1)%7) #Make Sunday=0 for day of week
    df['high_day_of_week_trading'] = high_ts.apply(lambda row: (row + timedelta(hours=7)).dayofweek) #Shift so that Day aligns with Trading Day
    df['high_hour_of_day'] = high_ts.dt.hour
    # df['high_hour_of_week'] =  high_ts.apply(lambda row: row.hour + ((row.dayofweek*24)))
    # df['high_hour_of_week_trading_sun_0'] =  high_ts.apply(lambda row: row.hour + ((((row + timedelta(hours=7)).dayofweek+1)%7)*24))
    # df['high_hour_of_week_sun_0'] =  high_ts.apply(lambda row: row.hour + (((row.dayofweek+ 1)%7)*24))
    df['high_hour_of_week_trading'] =  high_ts.apply(lambda row: ((row + timedelta(hours=7)).dayofweek*24) + (row + timedelta(hours=7)).hour) # 18:00 Sun = Hour 1 -> 16:00 Fri = 120
    df['high_minute_of_week_trading'] =  high_ts.apply(lambda row: ((row + timedelta(hours=7)).dayofweek*24) + ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60) 
    df['high_hour_of_day_trading'] =  high_ts.apply(lambda row:  (row + timedelta(hours=7)).hour)
    df['high_minute_of_day_trading'] =  high_ts.apply(lambda row: ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60)  
    df['high_minute_of_hour'] = high_ts.dt.minute
    df['high_minute_of_day'] = (high_ts.dt.hour * 60) + high_ts.dt.minute
    df['high_second_of_minute'] = high_ts.dt.second


    # Low Time Stamp
    low_ts = pd.to_datetime(df.low_timestamp)
    df['low_quarter_of_year'] = low_ts.dt.quarter
    df['low_month_of_year'] = low_ts.dt.month
    df['low_week_of_year'] = low_ts.dt.isocalendar().week
    df['low_week_of_month'] = low_ts.apply(week_of_month)
    df['low_day_of_year'] = low_ts.dt.dayofyear
    df['low_day_of_month'] = low_ts.dt.day
#     df['low_day_of_week'] = low_ts.dt.dayofweek
#     df['low_day_of_week_sun_0'] = low_ts.apply(lambda row: (row.dayofweek+ 1)%7)
    df['low_day_of_week_trading'] = low_ts.apply(lambda row: (row + timedelta(hours=7)).dayofweek)
    df['low_hour_of_day'] = low_ts.dt.hour
    # df['low_hour_of_week'] =  low_ts.apply(lambda row: row.hour + ((row + timedelta(hours=7)).dayofweek*24))
    # df['low_hour_of_week_sun_0'] =  low_ts.apply(lambda row: row.hour + (((row.dayofweek+ 1)%7)*24))
    df['low_hour_of_week_trading'] =  low_ts.apply(lambda row: ((row + timedelta(hours=7)).dayofweek*24) + (row + timedelta(hours=7)).hour)
    df['low_minute_of_week_trading'] =  low_ts.apply(lambda row: ((row + timedelta(hours=7)).dayofweek*24) + ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60) 
    df['low_hour_of_day_trading'] =  low_ts.apply(lambda row: (row + timedelta(hours=7)).hour) 
    df['low_minute_of_day_trading'] =  low_ts.apply(lambda row: ((row + timedelta(hours=7)).hour * 60) + (row + timedelta(hours=7)).minute - 60)   
    df['low_minute_of_hour'] = low_ts.dt.minute
    df['low_minute_of_day'] = (low_ts.dt.hour * 60) + low_ts.dt.minute
    df['low_second_of_minute'] = low_ts.dt.second
   
    

    atr_window = 50
    df['interval_range'] = df['high'] - df['low']
    df['interval_return'] = df['close'] - df['open']
    df['ATR'] = ta.volatility.average_true_range(high=df.high,low=df.low, close=df.close, window=atr_window)
    df['bullish'] = df.close >= df.open

    if tf_minutes == 10080: #'W1'
        df['high_proportion_of_interval'] =df.apply(weekHighProportionRow, axis=1)
        df['low_proportion_of_interval'] =df.apply(weekLowProportionRow, axis=1)
    elif tf_minutes==1440: #'D1'
        df['high_proportion_of_interval'] =df.apply(dayHighProportionRow, axis=1)
        df['low_proportion_of_interval'] =df.apply(dayLowProportionRow, axis=1)
    else:
        df['high_proportion_of_interval'] =df.apply(lambda row: intervalHighProportionRow(row, tf_minutes), axis=1)
        df['low_proportion_of_interval'] =df.apply(lambda row: intervalLowProportionRow(row, tf_minutes), axis=1)

    # display = df[['open','high','low', 'close','first_sample', 'last_sample', 'samples', 'month_of_year', 'week_of_year', 'week_of_month', 'day_of_year']]
    # display.head(20)

#     colnames_low = ['low_quarter_of_year', 'low_month_of_year', 'low_week_of_year', 'low_week_of_month', 'low_day_of_year', 'low_day_of_month', 'low_day_of_week', 'low_day_of_week_sun_0', 'low_day_of_week_trading', 'low_hour_of_day', 'low_minute_of_hour', 'low_minute_of_day', 'low_second_of_minute']
#     colnames_high = ['high_quarter_of_year', 'high_month_of_year', 'high_week_of_year', 'high_week_of_month', 'high_day_of_year', 'high_day_of_month', 'high_day_of_week', 'high_day_of_week_sun_0', 'high_day_of_week_trading', 'high_hour_of_day', 'high_minute_of_hour', 'high_minute_of_day', 'high_second_of_minute']

#     display = df[colnames_low]
#     display.describe()
#     # display.head(20)
    return df

def export_df_to_parquet(bars, instrument, tf):
    # export to Parquet
    start = time.time()
    dfFile = f"{baseDataPath}oanda_features_{instrument}_{tf}.parquet"
    bars.to_parquet(path=dfFile, index=True)
    end = time.time()
    return dfFile

def perform_feature_eng(instrument):
#     instrument = 'EUR_USD'

    # Weekly:
    tf = 'W1'
    tf_minutes = 10080 #week
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

    ## Daily:
    tf = 'D1'
    tf_minutes = 1440 #daily
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

     # 6 Hourly:
    tf = 'H6'
    tf_minutes = 360 #H6
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

     # 4 Hourly:
    tf = 'H4'
    tf_minutes = 240 #H4
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

    ## Hourly:
    tf = 'H1'
    tf_minutes = 60
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

    ## M15:
    tf = 'M15'
    tf_minutes = 15
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

    ## M5:
    tf = 'M5'
    tf_minutes = 5
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

    # ## M2:
    # tf = 'M2'
    # tf_minutes = 2
    # start = time.time()
    # perform_feature_eng_tf(instrument, tf, tf_minutes)
    # end = time.time()
    # print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')
    
    ## M1:
    tf = 'M1'
    tf_minutes = 1
    start = time.time()
    perform_feature_eng_tf(instrument, tf, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features Created and Serialised to Parquet in: {(end-start):.2f} seconds')

def perform_feature_eng_tf(instrument, tf, tf_minutes):
    
    # Load Data:
    start = time.time()
    df_tmp = loadIntervalDataframe(instrument, tf)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Parquet Loaded in: {(end-start):.2f} seconds')

    # Create Features:
    start = time.time()
    df_tmp = featureEng(df_tmp, tf_minutes)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Features engineered in: {(end-start):.2f} seconds')

    start = time.time()
    export_df_to_parquet(df_tmp, instrument, tf)
    end = time.time()
    print(f'{datetime.today().isoformat(" ","seconds")}: {instrument} - {tf} Serialised to Parquet in: {(end-start):.2f} seconds')
