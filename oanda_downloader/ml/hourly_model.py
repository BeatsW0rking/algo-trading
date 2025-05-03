#%% Imports
import math
import os
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
from sklearn import set_config
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Perceptron
from sklearn.pipeline import FeatureUnion, FunctionTransformer, Pipeline, make_pipeline, make_union
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, RobustScaler, StandardScaler, OrdinalEncoder, PowerTransformer, KBinsDiscretizer, QuantileTransformer, quantile_transform
from sklearn.model_selection import GridSearchCV, train_test_split, TimeSeriesSplit, cross_val_score, StratifiedKFold
from sklearn.metrics import confusion_matrix, RocCurveDisplay, f1_score, max_error, roc_curve, auc
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, precision_score, recall_score, roc_auc_score, root_mean_squared_error,r2_score, PredictionErrorDisplay, mean_absolute_error, median_absolute_error
from sklearn.compose import TransformedTargetRegressor, ColumnTransformer, make_column_transformer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.datasets import make_classification

import neptune
import neptune.integrations.sklearn as npt_utils
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier, XGBRegressor
import joblib

global API_TOKEN
global PROJECT
MODEL_FOLDER = 'models'

pd.options.mode.copy_on_write = True
random.seed(10765)
baseDataPath = '../data/'
set_config(transform_output = "pandas")

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


    
# %%
df_m1.index
# %%
df_m1.columns.values
# 'instrument', 'tf', 'open', 'high', 'low', 'close',
#        'high_timestamp', 'low_timestamp', 'first_sample', 'last_sample',
#        'samples', 'year', 'quarter_of_year', 'month_of_year',
#        'week_of_year', 'week_of_month', 'day_of_year', 'day_of_month',
#        'day_of_week', 'hour_of_day', 'minute_of_hour', 'minute_of_day',
#        'second_of_minute', 'high_year', 'high_quarter_of_year',
#        'high_month_of_year', 'high_week_of_year', 'high_week_of_month',
#        'high_day_of_year', 'high_day_of_month',
#        'high_day_of_week_trading', 'high_hour_of_day',
#        'high_hour_of_week_trading', 'high_minute_of_hour',
#        'high_minute_of_day', 'high_second_of_minute',
#        'low_quarter_of_year', 'low_month_of_year', 'low_week_of_year',
#        'low_week_of_month', 'low_day_of_year', 'low_day_of_month',
#        'low_day_of_week_trading', 'low_hour_of_day',
#        'low_hour_of_week_trading', 'low_minute_of_hour',
#        'low_minute_of_day', 'low_second_of_minute', 'interval_range',
#        'interval_return', 'ATR', 'bullish', 'high_proportion_of_interval',
#        'low_proportion_of_interval'

# Hourly:
'interval',
'open', 'high', 'low', 'close',
'day_of_week', 'hour_of_day', 'high_day_of_week_trading', 'high_minute_of_hour'
'interval_range', 'interval_return', 'ATR', 'bullish',
# Derived: 'Prior Interval Low / High'

# 1st, 2nd, 3rd, 4th, 5th Minute:
'interval',
'open', 'high', 'low', 'close',
# Derived: Low Rejection of Prior HTF Low, High Rejection of Prior HTF High, HTF Open -Low (Gone down?), High - HTF Open (GOne up?)

#%% - See what the latest date is in the DataFiles:
# tf= 'H1'
# datafile = f"{baseDataPath}oanda_{instrument}_{tf}.parquet"


# parquetSampleFile = f"{baseDataPath}oanda_data_pandas.parquet" 
# df_tmp = load_df_from_parquet(parquetSampleFile)
# df_tmp.query("instrument == 'NAS100_USD'").head()
db = Session(path="/tmp/oanda_data")
query_sql = f"""
    select instrument, min(timestamp) as first_sample, max(timestamp) as last_timestamp, count(*) as samples 
    from quant.ohlc
    --where instrument = 'NAS100_USD'
    group by instrument 
    limit 10
        """
res = db.query(query_sql, 'Dataframe') #, minutely=df_m, hourly=df_h)

dfrest = res
dfrest.head()
# %%

# 2024-08-26 23:00 - last Hour 
