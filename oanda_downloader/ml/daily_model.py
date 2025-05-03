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
df_weekly = loadDataSet(instrument, 'W1')
df_weekly['high_day_of_week_trading'] = day_names[df_weekly['high_day_of_week_trading']]
df_weekly['high_day_of_week_trading'] = pd.Categorical(df_weekly['high_day_of_week_trading'], categories=day_names)
df_weekly['low_day_of_week_trading'] = day_names[df_weekly['low_day_of_week_trading']]
df_weekly['low_day_of_week_trading'] = pd.Categorical(df_weekly['low_day_of_week_trading'], categories=day_names)


## Daily:
df_daily = loadDataSet(instrument, 'D1')
#TODO pull into Generation of PArquet Files.
df_daily = df_daily.rename(columns={"high_proportion_of_day": "high_proportion_of_interval", "low_proportion_of_day": "low_proportion_of_interval"}) 

## 4 Hourly:
df_4hourly = loadDataSet(instrument, 'H4')

## Hourly:
df_hourly = loadDataSet(instrument, 'H1')

# ## M15:
# df_m15 = loadDataSet(instrument, 'M15')

# ## M5:
# df_m5 = loadDataSet(instrument, 'M5')

# ## M1:
# df_m1 = loadDataSet(instrument, 'M1')

#%% Functions

def setup_Neptune():
    global API_TOKEN
    global PROJECT
    with open("../../secret/config-neptune.json", "r") as file:
        config = json.load(file)
    API_TOKEN=config["apiKey"]
    PROJECT='beats-working/NQ-Predict'
    
def add_features_to_df(df_base):
    # Add some Features:
    df_base['oh_range'] = df_base['high'] - df_base['open']
    df_base['ol_range'] = df_base['open'] - df_base['low']
    df_base['ch_range'] = df_base['high'] - df_base['close']
    df_base['cl_range'] = df_base['close'] - df_base['low']

    df_base['interval_range_return_ratio'] = df_base['interval_return'] / df_base['interval_range']

    df_base['oh_ol_ratio'] = df_base['oh_range'] / df_base['ol_range']
    df_base['oh_ch_ratio'] = df_base['oh_range'] / df_base['ch_range']
    df_base['oh_cl_ratio'] = df_base['oh_range'] / df_base['cl_range']
    df_base['ol_ch_ratio'] = df_base['ol_range'] / df_base['ch_range']
    df_base['ol_cl_ratio'] = df_base['ol_range'] / df_base['cl_range']
    df_base['ch_cl_ratio'] = df_base['ch_range'] / df_base['cl_range']

    df_base['oh_interval_range_ratio'] = df_base['oh_range'] / df_base['interval_range']
    df_base['oh_interval_return_ratio'] = df_base['oh_range'] / df_base['interval_return']
    df_base['oh_ATR_ratio'] = df_base['oh_range'] / df_base['ATR']

    df_base['ol_interval_range_ratio'] = df_base['ol_range'] / df_base['interval_range']
    df_base['ol_interval_return_ratio'] = df_base['ol_range'] / df_base['interval_return']
    df_base['ol_ATR_ratio'] = df_base['ol_range'] / df_base['ATR']

    df_base['ch_interval_range_ratio'] = df_base['ch_range'] / df_base['interval_range']
    df_base['ch_interval_return_ratio'] = df_base['ch_range'] / df_base['interval_return']
    df_base['ch_ATR_ratio'] = df_base['ch_range'] / df_base['ATR']

    df_base['cl_interval_range_ratio'] = df_base['cl_range'] / df_base['interval_range']
    df_base['cl_interval_return_ratio'] = df_base['cl_range'] / df_base['interval_return']
    df_base['cl_ATR_ratio'] = df_base['cl_range'] / df_base['ATR']
    
    return df_base

def add_shifted_column(df, c, i):
    dfnew = pd.DataFrame()
    dfnew[f'{c}_shift_{i}'] = df[c].shift(i)
    return dfnew

def add_shifted_ratio_column(df, c, i):
    dfnew = pd.DataFrame()
    dfnew[f'{c}_ratio_{i}'] = df[c].shift(i) / df[c]
    return dfnew

def add_ratio_column(df, c, d):
    dfnew = pd.DataFrame()
    dfnew[f'{d}_{c}_ratio'] = df[c] / df[d] #add np.abs()?
    return dfnew

def create_shifted_columns(df, columns, shift_count, drop_na=False):
    
    x=shift_count +1
    new_columns = []
    
    for i in range(1,x):
        new_df_tmp = pd.concat([add_shifted_column(df, c, i) for c in columns], axis=1)
        df = df = pd.concat([df,  new_df_tmp], axis=1)
        new_columns = new_columns + [f'{c}_shift_{i}' for c in columns]
    if drop_na: 
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.dropna()
    new_df = df.copy()
    
    return new_df, new_columns

def create_shifted_ratio_columns(df, columns, shift_count, drop_na=False):
    x=shift_count +1
    new_columns = []
    for i in range(1,x):
        new_df_tmp = pd.concat([add_shifted_ratio_column(df, c, i) for c in columns], axis=1)
        df = pd.concat([df,  new_df_tmp], axis=1)
        new_columns = new_columns + [f'{c}_ratio_{i}' for c in columns]
    if drop_na: 
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.dropna()
    new_df = df.copy()
    
    return new_df, new_columns

def getTrainTestData(df, feature_cols, target_col, holdback_proportion):
    X = df[feature_cols]
    Y = pd.Series(df[target_col])
    # Y_class = pd.Series(df[target_col_class])

    # X contains features, y contains target labels
    # X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=42) - Only use if no prior info engineered into features last period x ADR etc

    #Split off last 20% of Data for OOS Testing of Model.
    test_size = int(X.shape[0] - (X.shape[0] * holdback_proportion))
    x_test = X.iloc[test_size:]
    x_train = X.iloc[:test_size]
    y_test = Y.iloc[test_size:]
    y_train = Y.iloc[:test_size]
    
    return x_test, x_train, y_test, y_train

def getFeatureEngineeredTestTrainData(source_df, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback):
    # intervals_lookback = 5
    holdback_proportion = 0.2
    
    source_df = add_features_to_df(source_df)
    
    df_ml = source_df[descriptive_cols + end_of_period_num_cols + end_of_period_cat_cols] 

    df_ml, new_num_features = create_shifted_ratio_columns(df_ml, end_of_period_num_cols, intervals_lookback)
    end_of_period_num_cols = end_of_period_num_cols + new_num_features
        
    df_ml, new_num_features = create_shifted_columns(df_ml, end_of_period_num_cols, intervals_lookback)
    numeric_features = new_num_features

    df_ml, new_cat_features = create_shifted_columns(df_ml, end_of_period_cat_cols, intervals_lookback, drop_na=True)
    categorical_features = descriptive_cols + new_cat_features

    feature_cols = categorical_features + numeric_features

    x_test, x_train, y_test, y_train = getTrainTestData(df_ml, feature_cols, target_col, holdback_proportion)
    
    return x_test, x_train, y_test, y_train, categorical_features, numeric_features
    
setup_Neptune()  

#%% Feature Column Lists
descriptive_cols = [
    'quarter_of_year', 
    'month_of_year', 
    'week_of_year', 
    'week_of_month',
    'day_of_year', 
    'day_of_month', 
    'day_of_week',
    'hour_of_day',
    'minute_of_hour', 
    'minute_of_day', 
    'second_of_minute']

# Targets
orig_end_of_period_num_cols =[
    'open',
    'high',
    'low',
    'close',   
]

end_of_period_num_cols = [
    'interval_range',
    'interval_return',
    'ATR',
    'high_proportion_of_interval', 
    'low_proportion_of_interval',
    'oh_range',
    'ol_range',
    'ch_range',
    'cl_range',
    'interval_range_return_ratio',
    'oh_ol_ratio',
    'oh_ch_ratio',
    'oh_cl_ratio',
    'ol_ch_ratio',
    'ol_cl_ratio',
    'ch_cl_ratio',
    'oh_interval_range_ratio',
    'oh_interval_return_ratio',
    'oh_ATR_ratio',
    'ol_interval_range_ratio',
    'ol_interval_return_ratio',
    'ol_ATR_ratio',
    'ch_interval_range_ratio',
    'ch_interval_return_ratio',
    'ch_ATR_ratio',
    'cl_interval_range_ratio',
    'cl_interval_return_ratio',
    'cl_ATR_ratio'
    ]

end_of_period_cat_cols = [
    'bullish',
    'high_year',
    'high_quarter_of_year', 
    'high_month_of_year', 
    'high_week_of_year',
    'high_week_of_month', 
    'high_day_of_year', 
    'high_day_of_month',
    'high_day_of_week_trading', 
    'high_hour_of_day',
    'high_hour_of_week_trading', 
    'high_minute_of_hour',
    'high_minute_of_day', 
    'high_second_of_minute', 
    'low_quarter_of_year',
    'low_month_of_year', 
    'low_week_of_year', 
    'low_week_of_month',
    'low_day_of_year', 
    'low_day_of_month', 
    'low_day_of_week_trading',
    'low_hour_of_day',
    'low_hour_of_week_trading', 
    'low_minute_of_hour',
    'low_minute_of_day', 
    'low_second_of_minute']
######  

#%% Pipeline Transformers
# df_daily.head()
# dft = df_daily.copy(deep=True)
# dft['open_shift'] = dft['open'].shift(1)
# dft.head()
# Get all permutations of [1, 2, 3] 
from itertools import combinations 
comb = combinations (['open','high', 'low', 'close'], 2) 
 
# Generate Ranges Features for passed in Feature Permutations
for i in list(comb): 
    print(f'{i[0][0]}{i[1][0]}_range') 


class Debugger(TransformerMixin, BaseEstimator):
    def transform(self, data):
        print("Shape of Pre-processed Data:", data.shape)
        print(pd.DataFrame(data).head())
        return data
    def fit(self, data, y=None, **fit_params):
        return self

class FeatureSelector(TransformerMixin, BaseEstimator):
    def __init__(self, feature_names):
        self.feature_names = feature_names   
    def fit( self, X, y = None ):
        # X = self._validate_data(X, accept_sparse=True)
        return self
    def transform(self, X, y=None):
        # self._validate_data(X, accept_sparse=True, reset=False)
        return X[self.feature_names].copy(deep=True)
    
class FeatureShifter(TransformerMixin, BaseEstimator):
    def __init__(self, feature_names=None, intervals=1, drop_orig_features=True,  drop_na=False):
        self.feature_names = feature_names
        self.intervals = intervals
        self.drop_na = drop_na
        self.drop_orig_features = drop_orig_features 
        self.output_features = []  
    def fit( self, X, y = None ):
        # print(f'feature_names: {self.feature_names}')
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
        # print(f'feature_names: {self.feature_names}')
        _, new_num_features = create_shifted_columns(X, self.feature_names, self.intervals, drop_na=self.drop_na)
        self._validate_data(X, accept_sparse=True)
        if self.drop_orig_features:
            self.output_features.extend(new_num_features)
        else:
            self.output_features.extend(self.feature_names)
            self.output_features.extend(new_num_features)
        return self
    def transform(self, X, y=None):
        self._validate_data(X, accept_sparse=True, reset=False)  
        df, new_num_features = create_shifted_columns(X, self.feature_names, self.intervals, drop_na=self.drop_na)
        df = df[self.output_features].copy(deep=True)
        return df         
    def get_feature_names_out(self, input_features=None):
        return self.output_features
        
class FeatureShiftedRatio(TransformerMixin, BaseEstimator):
    def __init__(self, feature_names=None, intervals=1, drop_orig_features=True, drop_na=False):
        self.feature_names = feature_names
        self.intervals = intervals
        self.drop_orig_features = drop_orig_features 
        self.drop_na = drop_na  
        self.output_features = [] 
    def fit( self, X, y = None ):
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
        self._validate_data(X, accept_sparse=True)
        if not self.drop_orig_features:
            self.output_features.extend(self.feature_names)     
        _, new_num_features = create_shifted_ratio_columns(X, self.feature_names, self.intervals, drop_na=self.drop_na)
        self.output_features.extend(new_num_features)
        return self
    def transform(self, X, y=None):
        self._validate_data(X, accept_sparse=True, reset=False)
        df, _ = create_shifted_ratio_columns(X, self.feature_names, self.intervals, drop_na=self.drop_na)
        return df[self.output_features].copy(deep=True)
    def get_feature_names_out(self, input_features=None):
        return self.output_features

class RangeFeatureTransformer(TransformerMixin, BaseEstimator):
    
    def __init__(self, feature_names=None, drop_orig_features=True):
        self.feature_names = feature_names
        self.output_features = []
        self.drop_orig_features = drop_orig_features
    def fit( self, X, y = None ):
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
         
        self._validate_data(X, accept_sparse=True)
        if not self.drop_orig_features:
            self.output_features.extend(self.feature_names)
        perm = combinations(self.feature_names, 2) 
        for i in list(perm):
            new_feature_name = f'{i[0][0]}{i[1][0]}_range' 
            self.output_features.append(new_feature_name)
        return self
    def transform(self, X, y=None):
        if self.feature_names is not None:
            X = X[self.feature_names]
        self._validate_data(X, accept_sparse=True, reset=False)
        # Get all permutations of self.feature_names
        perm = combinations(self.feature_names, 2) 
        # Generate Ranges Features for passed in Feature Combinations
        for i in list(perm):
            new_feature_name = f'{i[0][0]}{i[1][0]}_range' 
            X[new_feature_name] = X[i[1]] - X[i[0]]
  
        return X[self.output_features].copy(deep=True)
    def get_feature_names_out(self, input_features=None):
        return self.output_features

class RatioFeatureTransformer(TransformerMixin, BaseEstimator):
    def __init__(self, feature_names=None, drop_orig_features=True):
        self.feature_names = feature_names
        self.output_features = []
        self.drop_orig_features = drop_orig_features
    def fit( self, X, y = None ):
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
         
        self._validate_data(X, accept_sparse=True)
        if not self.drop_orig_features:
            self.output_features.extend(self.feature_names)
        perm = combinations(self.feature_names, 2) 
        for i in list(perm):
            new_feature_name = f'{i[0]}_{i[1]}_ratio' 
            self.output_features.append(new_feature_name)
        return self
    def transform(self, X, y=None):
        self._validate_data(X, accept_sparse=True, reset=False)
        # Get all permutations of self.feature_names
        perm = combinations(self.feature_names, 2) 
        # Generate Ranges Features for passed in Feature Combinations
        new_df = pd.DataFrame()
        # for i in list(perm): 
        #     new_df[f'{i[0]}_{i[1]}_ratio'] = np.abs(X[i[1]] / X[i[0]])
        new_df = pd.concat([add_ratio_column(X, i[1], i[0]) for i in list(perm)], axis=1)
            
        X = pd.concat([X, new_df], axis=1)
        X.replace([np.inf, -np.inf], np.nan, inplace=True)
        # X = X.dropna()
           
        return X[self.output_features].copy(deep=True)
    def get_feature_names_out(self, input_features=None):
        return self.output_features
    
class ATRFeatureTransformer(TransformerMixin, BaseEstimator):
    def __init__(self, windows, feature_names=None, drop_orig_features=True):
        self.feature_names = feature_names
        self.output_features = []
        self.drop_orig_features = drop_orig_features
        self.windows = windows
    def fit( self, X, y = None ):
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
         
        self._validate_data(X, accept_sparse=True)
        if not self.drop_orig_features:
            self.output_features.extend(self.feature_names)
        for window in self.windows:
            new_feature_name = f'ATR{window}'
            self.output_features.append(new_feature_name)
        return self
    def transform(self, X, y=None):
        self._validate_data(X, accept_sparse=True, reset=False)
        for window in self.windows:
            X[f'ATR{window}'] = ta.volatility.average_true_range(high=X.high,low=X.low, close=X.close, window=window)
           
        return X[self.output_features].copy(deep=True)
    def get_feature_names_out(self, input_features=None):
        return self.output_features

class FailedExpansionFeatureTransformer(TransformerMixin, BaseEstimator):
    def __init__(self, feature_names=None, drop_orig_features=True):
        self.feature_names = feature_names
        self.output_features = []
        self.drop_orig_features = drop_orig_features
    def fit( self, X, y = None ):
        if self.feature_names is None:
            self.feature_names =  X.columns.values
        else:
           X = X[self.feature_names] 
         
        self._validate_data(X, accept_sparse=True)
        if not self.drop_orig_features:
            self.output_features.extend(self.feature_names)
        self.output_features.extend(['failed_exp_higher', 'failed_exp_lower'])
        return self
    def transform(self, X, y=None):
        self._validate_data(X, accept_sparse=True, reset=False)
        # Bool H[0] > H[1] and C[0] < H[1]
        # Bool L[0] < L[0] and C[0] > L[1]
        X[f'failed_exp_higher'] = (X.high > X.high.shift(1)) & (X.close < X.high.shift(1))
        X[f'failed_exp_lower'] = (X.low < X.low.shift(1)) & (X.close > X.low.shift(1))
           
        return X[self.output_features].copy(deep=True)
    def get_feature_names_out(self, input_features=None):
        return self.output_features
    
#%% Preprocessing Pipeline
holdback_proportion=0.2
intervals_lookback = 1 
target_col = 'bullish'

numerical_features = orig_end_of_period_num_cols
categorical_features = descriptive_cols + end_of_period_cat_cols
original_cols = numerical_features + categorical_features

# df_daily, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)
x_train, x_test, y_train, y_test = getTrainTestData(df_daily, original_cols, target_col, holdback_proportion)



    
numerical_pipeline = Pipeline(steps = [ 
    ("num_selector", FeatureSelector(numerical_features)),
    ("imputer", SimpleImputer(strategy="median")),
    ("std_scaler", StandardScaler()) 
])

numerical_shifted_pipeline = Pipeline(steps = [ 
    ("num_selector", FeatureSelector(numerical_features)),
    # ('debug0', Debugger()),
    ("num_ratio_shifter", FeatureShiftedRatio(intervals=intervals_lookback)),
    # ('debug1', Debugger()),
    ("imputer1", SimpleImputer(strategy="median")),
    ("num_shifter", FeatureShifter(intervals=intervals_lookback, drop_na=False)),
    # ('debug2', Debugger()),
    ("imputer2", SimpleImputer(strategy="median")),
    # ('debug3', Debugger()),
    ("std_scaler", StandardScaler()),
    # ('debug4', Debugger()), 
])

ct =  ColumnTransformer([('shifter',FeatureShifter(intervals=intervals_lookback, drop_na=False), end_of_period_cat_cols)],
                                                remainder='passthrough', verbose_feature_names_out=False)
ct.set_output(transform='pandas')

categorical_pipeline = Pipeline(steps = [
    ("cat_selector", FeatureSelector(categorical_features)),
    ('shift_end of interval', ct), 
    
    ("ohe", OneHotEncoder(
        handle_unknown="ignore", sparse_output=False,
        # categories=[
        #     df_daily["day_of_week"].unique()
        # ]
        )
    ) 
])

class DailyTrendFeature(BaseEstimator, TransformerMixin):
    def __init__(self):
        pass
    def fit( self, X, y = None ):
        return self
    def transform(self, X, y=None):
        X["open_close_delta"] = X["close"] / X["open"]
        def daily_trend(row):
            if 0.99 > row["open_close_delta"]: # assume 'down' day when prices fall > 1% from open
                row["daily_trend"] = "down"
            elif 1.01 < row["open_close_delta"]: # assume 'up' day when prices rise > 1% from open
                row["daily_trend"] = "up"
            else:
                row["daily_trend"] = "flat"
            return row
        X = X.apply(daily_trend, axis=1)
        return X

daily_trend_feature_pipeline = Pipeline(steps = [ 
    ("selector", FeatureSelector(["open", "close"])),
    ("feature_engineering", DailyTrendFeature()),
    ("selector_new", FeatureSelector(["daily_trend"])),
    ("ohe", OneHotEncoder(
        handle_unknown="ignore", sparse_output=False,
        categories=[
            ["up", "down", "flat"],
        ])
    ) 
])

def test_new_feature_pipeline(train_df):
    test_df = train_df.sample(15).copy(deep=True).reset_index()
    print(test_df['day_of_week'])
    sample_transforms = daily_trend_feature_pipeline.fit_transform(
        test_df, 
        test_df[target_col]
    )
    features = daily_trend_feature_pipeline.named_steps["ohe"].get_feature_names_out()
    df = pd.DataFrame(sample_transforms, columns =features)
    print(df)

test_new_feature_pipeline(df_daily)

feature_pipeline = FeatureUnion(
    # n_jobs=-1, 
    transformer_list=[ 
        ("numerical_pipeline", numerical_shifted_pipeline),
        ("categorical_pipeline", categorical_pipeline),
        ("daily_trend_feature_pipeline", daily_trend_feature_pipeline),
    ]
)

def test_feature_pipeline(train_df):
    test_df = train_df.sample(15).copy(deep=True).reset_index()
    # print(test_df)
    feature_pipeline.fit(test_df, test_df[target_col])
    print(pd.DataFrame(feature_pipeline.transform(test_df)) )#, #.toarray(),
            # columns = (
            #     numerical_features 
            #     + list(feature_pipeline.transformer_list[1][1]["ohe"].get_feature_names_out())
            #     + list(feature_pipeline.transformer_list[2][1]["ohe"].get_feature_names_out())
            # )
        # )
    # )
test_feature_pipeline(df_daily)

model_pipeline = Pipeline(steps=[
    ("feature_pipeline", feature_pipeline),
    ("std_scaler", StandardScaler()),
    ("model", LogisticRegression())
])
param_grid = [
    {
        # "feature_pipeline__numerical_pipeline__imputer__strategy": ["mean", "median"],
        "model": [LogisticRegression()],
        "model__C": [0.1, 1.0, 10],
    },
    {
        # "feature_pipeline__numerical_pipeline__imputer__strategy": ["mean", "median"],
        "model": [RandomForestClassifier()],
        'model__n_estimators': [10, 50 ,100, 200],
        "model__max_depth": [1, 3, 5, 7],
    }
]
grid_search = GridSearchCV(
    model_pipeline, 
    param_grid, 
    cv=TimeSeriesSplit(n_splits=5),
    scoring="roc_auc",
    refit=True,
    # n_jobs=-1
)

now = datetime.now()
grid_search.fit(x_train, y_train)
print(datetime.now() - now)

print(f"Best params: {grid_search.best_params_}")
print(f"Best score: {grid_search.best_score_}")

auc_score_train = roc_auc_score(
    y_true=y_train,
    y_score=grid_search.predict(x_train),
    average="weighted"
)

auc_score_test = roc_auc_score(
    y_true=y_test,
    y_score=grid_search.predict(x_test),
    average="weighted"
)

print(f'AUC Score Train: {auc_score_train:.2f}, AUC Score Test: {auc_score_test:.2f}')

# %%

#Actual Pipeline:

# cachedir = mkdtemp()
# pipe = Pipeline(estimators, memory=cachedir)

# Date Index + OHLC -> 
#  Compute Ranges and Returns = RangeTransformer
    # O-C = Return
    # H-L = Range
    # H-O = oh_range = df_base['high'] - df_base['open']
    # O-L = oh_range = df_base['open'] - df_base['low']
    # H-C = ch_range = df_base['high'] - df_base['close']
    # C-L = cl_range = df_base['close'] - df_base['low']
    
    # 'interval_range_return_ratio'] = df_base['interval_return'] / df_base['interval_range'] 
    # C/O = CO Ratio (% Change)
    # H/L = HL Ratio (% Range)
    
    # 'range_oh_ratio' = range / df_base['oh_range']
    # 'range_ol_ratio' = range / ol_range
    # 'range_ch_ratio' = range / ch_range
    # 'range_cl_ratio' = range / cl_range
    
    # return_oh_ratio = return / oh_range
    # return_ol_ratio = return / ol_range
    # return_ch_ratio = return / ch_range
    # return_cl_ratio = return / cl_range
    
    # 'oh_ol_ratio' = df_base['oh_range'] / df_base['ol_range']
    # 'oh_ch_ratio' = df_base['oh_range'] / df_base['ch_range']
    # 'oh_cl_ratio' = df_base['oh_range'] / df_base['cl_range']
   
    # 'ol_ch_ratio' = df_base['ol_range'] / df_base['ch_range']
    # 'ol_cl_ratio' = df_base['ol_range'] / df_base['cl_range']
    # 'ch_cl_ratio' = df_base['ch_range'] / df_base['cl_range']
    
    # ATR 5
    # ATR 10
    # ATR 50
    
    # df_base['oh_ATR_5_ratio'] = df_base['oh_range'] / df_base['ATR_5']
    # df_base['ol_ATR_5_ratio'] = df_base['ol_range'] / df_base['ATR_5']
    # df_base['ch_ATR_5_ratio'] = df_base['ch_range'] / df_base['ATR_5']
    # df_base['cl_ATR_5_ratio'] = df_base['cl_range'] / df_base['ATR_5']
    
    # df_base['oh_ATR_5_ratio'] = df_base['oh_range'] / df_base['ATR_5']
    # df_base['ol_ATR_5_ratio'] = df_base['ol_range'] / df_base['ATR_5']
    # df_base['ch_ATR_5_ratio'] = df_base['ch_range'] / df_base['ATR_5']
    # df_base['cl_ATR_5_ratio'] = df_base['cl_range'] / df_base['ATR_5']
    
    # df_base['oh_ATR_5_ratio'] = df_base['oh_range'] / df_base['ATR_5']
    # df_base['ol_ATR_5_ratio'] = df_base['ol_range'] / df_base['ATR_5']
    # df_base['ch_ATR_5_ratio'] = df_base['ch_range'] / df_base['ATR_5']
    # df_base['cl_ATR_5_ratio'] = df_base['cl_range'] / df_base['ATR_5']
    
    # Diff 1, 2, 3, 4, 5, x
    # Open High Low Close Range Return
    
    # Bool H[0] > H[1] and C[0] < H[1]
    # Bool L[0] < L[0] and C[0] > L[1]
    
    # Stationarity check and adjustments
    # For OHLC & Intervals and Ranges
    
    
    # LTF Daily -> H1 
    # LTF Range, Return, Interval Ordinal, Higher than Prior HTF Interval High, Lower than Prior HTF Interval Low, Higher than Current HTF Interval Open
    
    # Asian Range 20:00 - 00:00
    # H6 6AM Range 06:00 - 12:00
    
    # Workflow:
    #  Add Feature to Pipeline
    #  Add Tage for Neptune
    #  Record Run in Neptune - no lagged / 1 lagged / 5 lagged
    #  Compare Results
    #  Steps can be skipped by settingn them to 'passthrough' in a gridsearch param dict
    
    # Pipeline Arch:
    #  Numeric Features:
    #  DONE: OHLC -> RangeFeatureTransformer -> RangeFeatures 
    #  DONE: RangeFeatures + OHLC -> RatioFeatureTransformer -> RatioFeatures
    #  DONE: OHLC -> ATRFeatureTransformer -> ATRFeatures
    #  DONE: RatioFeatures + ATRFeatures -> RatioFeatureTransformer -> ATRRatioFeatures
    #  DONE: OHLC -> LaggedDiffFeatureTransformer -> LaggedDiffFeatures 
    #  DONE: OHLC -> FailedExpansionFeatureTransformer -> FailedExpansionFeatures
    #  DONE: High/Low Proportion of Interval -> 
    # 
    # Categorical Features:
    # Sin Cos encoding of Hours / Days / Weeks / Months / High of Day / Low of Day
    
    # Lagged values of Bullish and FailedExpansionFeatures
descriptive_cols = [
    'quarter_of_year', 
    'month_of_year', 
    'week_of_year', 
    'week_of_month',
    'day_of_year', 
    'day_of_month', 
    'day_of_week',
    'hour_of_day',
    'minute_of_hour', 
    'minute_of_day', 
    'second_of_minute']

end_of_period_cat_cols = [
    'bullish',
    'high_year',
    'high_quarter_of_year', 
    'high_month_of_year', 
    'high_week_of_year',
    'high_week_of_month', 
    'high_day_of_year', 
    'high_day_of_month',
    'high_day_of_week_trading', 
    'high_hour_of_day',
    'high_hour_of_week_trading', 
    'high_minute_of_hour',
    'high_minute_of_day', 
    'high_second_of_minute', 
    'low_quarter_of_year',
    'low_month_of_year', 
    'low_week_of_year', 
    'low_week_of_month',
    'low_day_of_year', 
    'low_day_of_month', 
    'low_day_of_week_trading',
    'low_hour_of_day',
    'low_hour_of_week_trading', 
    'low_minute_of_hour',
    'low_minute_of_day', 
    'low_second_of_minute']
#%%
# p = make_pipeline(RangeFeatureTransformer(['open', 'close', 'low', 'high'], drop_orig_features=True))
# p.fit(df_daily)
# df = p.transform(df_daily)
# df.head()

#  FeatureSelector(['open', 'close', 'low', 'high']),
#     ATRFeatureTransformer(windows=[5,10,50], drop_orig_features=False),
#     RangeFeatureTransformer(['open', 'close', 'low', 'high'], drop_orig_features=False), 
#     RatioFeatureTransformer(drop_orig_features=False),
#     SimpleImputer(strategy="median"),
#     FeatureShifter(intervals=5, drop_orig_features=True, drop_na=False),
#     SimpleImputer(strategy="median")
def diffFeatureNames(self, input_features):
   p = self.kw_args['periods']
   output_features =  [f'{f}_diff{p}' for f in input_features]
   return output_features
c = Pipeline([
    ('cat', ColumnTransformer([
                ('cat_p', Pipeline([
                    ('fe', FeatureShifter(intervals=5, drop_orig_features=True, drop_na=False)),
                    # ('fe', FeatureShifter(intervals=1, drop_orig_features=True, drop_na=False)),
                    ]), end_of_period_cat_cols),
                                        # ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), descriptive_cols),
                                        ], 
                remainder='passthrough', verbose_feature_names_out=False)),    
])

n = Pipeline([
        ('f1', FeatureUnion([
            ('c1', ColumnTransformer([('atr', ATRFeatureTransformer(windows=[5,10,50], drop_orig_features=True), ['open', 'close', 'low', 'high']),], 
                remainder='drop', verbose_feature_names_out=False)),
            ('cex', ColumnTransformer([('fex', FailedExpansionFeatureTransformer(drop_orig_features=True), ['open', 'close', 'low', 'high']),], 
                remainder='drop', verbose_feature_names_out=False)),
            ('Pipe', Pipeline([
                ('c2', ColumnTransformer([
                    # ('feat1', FeatureSelector(['open', 'close', 'low', 'high'])),
                    ('range', RangeFeatureTransformer(drop_orig_features=False), ['open', 'close', 'low', 'high']),
                    ],  
                    remainder='passthrough', verbose_feature_names_out=False)),
                # ('rs', RobustScaler()),
                # ('c5', ColumnTransformer([
                #     ('log1', FunctionTransformer(pd.DataFrame.diff, kw_args={'periods': 1}, feature_names_out=diffFeatureNames), ['open', 'close', 'low', 'high']),
                #     # ('log1', FunctionTransformer(diff), ['open', 'close', 'low', 'high']),
                #     ],  
                #     remainder='passthrough', verbose_feature_names_out=False)),
                # ('c3', ColumnTransformer([
                #     ('log1', FunctionTransformer(np.cbrt), ['ch_range', 'oh_range', 'lh_range', 'ol_range', 'cl_range'])#, 'oh_range_lh_range_ratio']),
                #     ],  
                #     remainder='passthrough', verbose_feature_names_out=False)),
                # ('c4', ColumnTransformer([
                #     ('log1', FunctionTransformer(np.log1p), ['oh_range_lh_range_ratio']),
                #     ],  
                #     remainder='passthrough', verbose_feature_names_out=False)),
                # ('f1_log', FunctionTransformer(np.log1p))
             
            ])),
        ], verbose_feature_names_out=False)),
       
        # ('rs', RobustScaler()),
        
       
        # ('pwr', PowerTransformer(method='yeo-johnson')),
        # ('qs', QuantileTransformer(n_quantiles=20)),
        
        # ('scaler0', StandardScaler()),
        
         ('f2', FeatureUnion([
                ('log1', FunctionTransformer(pd.DataFrame.diff, kw_args={'periods': 1}, feature_names_out=diffFeatureNames)),
                ('log2', FunctionTransformer(pd.DataFrame.diff, kw_args={'periods': 5}, feature_names_out=diffFeatureNames)),
                ('log3', FunctionTransformer(pd.DataFrame.diff, kw_args={'periods': 10}, feature_names_out=diffFeatureNames)),
                # ('srrs', SimpleImputer(strategy="median")),
        ], verbose_feature_names_out=False)),
        # ('srr', SimpleImputer(strategy="median")),
        
        # ('r', RatioFeatureTransformer(drop_orig_features=False)),
        
        # ('rs', RobustScaler()), 
        # ('pwr', PowerTransformer(method='yeo-johnson')),
      
        # ('qs', QuantileTransformer(n_quantiles=50, output_distribution='normal')),
        ('s', SimpleImputer(strategy="median")),
        ('fe', FeatureShifter(intervals=5, drop_orig_features=True, drop_na=False)),
        ('ss', SimpleImputer(strategy="mean")),
        # ('pca', TruncatedSVD(n_components=10, n_iter=7, random_state=42)),
        # ('scaler', StandardScaler()),
        
    ])



# df_daily, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)
numerical_features = ['open', 'close', 'low', 'high', 'high_proportion_of_interval', 'low_proportion_of_interval']
input_cols =  numerical_features + descriptive_cols + end_of_period_cat_cols  # ['open', 'close', 'low', 'high']    'high_proportion_of_interval', 'low_proportion_of_interval',
target_col = 'bullish'

p = Pipeline([
        ('af', ColumnTransformer([
                ('numeric', n, numerical_features), 
                ('cat', c, descriptive_cols + end_of_period_cat_cols)
                ], remainder='drop', verbose_feature_names_out=False))
])

holdback_proportion = 0.2

x_train, x_test, y_train, y_test = getTrainTestData(df_daily, input_cols, target_col, holdback_proportion)

x_train.head(20)

p.fit(df_daily[input_cols])
df = p.transform(df_daily[input_cols])
df.head(30)
df.describe()
df.hist(figsize=(50,50))
p

model_pipeline = Pipeline(steps=[
    ("feature_pipeline", p),
    ("model", LogisticRegression())
])
param_grid = [
    # {
    #     # "feature_pipeline__ratiofeaturetransformer": ['passthrough', RatioFeatureTransformer(['open', 'close', 'low', 'high'], drop_orig_features=False)],
    #     "model": [LogisticRegression()],
    #     "model__C": [1.0, 15, 20],
    # },
    {
        # "feature_pipeline__rangefeaturetransformer": ['passthrough'], #, RangeFeatureTransformer(['open', 'close', 'low', 'high'], drop_orig_features=False)],
        # "feature_pipeline__atrfeaturetransformer": ['passthrough', ATRFeatureTransformer(windows=[5], drop_orig_features=False), ATRFeatureTransformer(windows=[10], drop_orig_features=False), ATRFeatureTransformer(windows=[50], drop_orig_features=False)],
        # "feature_pipeline__ratiofeaturetransformer": ['passthrough'], #, RatioFeatureTransformer(drop_orig_features=False)],
        # "feature_pipeline__featureshifter": [FeatureShifter(intervals=3, drop_orig_features=True, drop_na=False), FeatureShifter(intervals=5, drop_orig_features=True, drop_na=False), FeatureShifter(intervals=10, drop_orig_features=True, drop_na=False)], 
        #"feature_pipeline__numerical_pipeline__imputer__strategy": ["mean", "median"],
        "model": [RandomForestClassifier()],
        'model__n_estimators': [1000, 2000, 500],
        "model__max_depth": [5, 7],
        'model__max_features': ['log2'],
        'model__min_samples_leaf': [3,4],
        'model__min_samples_split': [14, 16],
    },
    # {
    #     "model": [RandomForestClassifier()],
    #     'model__n_estimators': [1000, 10000],
    #     "model__max_depth": [1,5, 10],
    # }
]
grid_search = GridSearchCV(
    model_pipeline, 
    param_grid, 
    cv=TimeSeriesSplit(n_splits=5),
    scoring="roc_auc",
    refit=True,
    # n_jobs=-1
)



now = datetime.now()
grid_search.fit(x_train, y_train)
print(datetime.now() - now)

clf = grid_search.best_estimator_['model']
feature_names = clf.feature_names_in_

print(f"Best params: {grid_search.best_params_}")
print(f"Best score: {grid_search.best_score_}")

auc_score_train = roc_auc_score(
    y_true=y_train,
    y_score=grid_search.predict(x_train),
    average="macro"
)

auc_score_test = roc_auc_score(
    y_true=y_test,
    y_score=grid_search.predict(x_test),
    average="macro"
)
print(f'AUC Score Train: {auc_score_train:.2f}, AUC Score Test: {auc_score_test:.2f}')


plt.figure(figsize=(40,40))
fig, _ = plt.subplots(1, 1, figsize=(15, 25))
importances = clf.feature_importances_
df3=pd.DataFrame({'allvarlist':feature_names,'importances':importances})
df3.sort_values('importances',inplace=True)
df3t = df3.iloc[max(df3.shape[0] - 40, 0):]
plt.barh(df3t.allvarlist,df3t.importances)
plt.show()
# %% LTF SQL

df_d = df_daily.copy(deep=True)
df_d.reset_index(names='interval', inplace=True)

query_sql = f"""
    select s.interval, s.dopen, s.high, s.low, s.close, s.open
    --[1] as h1_open,
    --[2] as h2_open
    from  
    (
     select 
        interval as interval, open as dopen, high as high, low as low, close as close, h.open as open,
         row_number() over(partition by day(h.interval) order by h.interval) rn 
     from 
        (select * from __daily__ as d inner join __hourly__ as h on day(d.interval) = day(h.interval))
     )s
    PIVOT
    (MAX(open) for rn in ([1],[2])) p
    ;
    """
res = cdf.query(sql=query_sql, daily=df_d, hourly=df_hourly)

dfres = res.to_pandas()
dfres.head()
    
# %%
