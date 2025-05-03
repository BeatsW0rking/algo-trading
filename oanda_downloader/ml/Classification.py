#%% Imports
import os
import numpy as np
import pandas as pd
import random
import seaborn as sns
import time
import json
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
# import chdb -- needs Linux / OSX
# from chdb.session import Session
# import chdb.dataframe as cdf
from pathlib import Path
from sklearn import set_config
from sklearn.linear_model import LogisticRegression, Perceptron
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler, OrdinalEncoder, PowerTransformer, KBinsDiscretizer, QuantileTransformer, quantile_transform
from sklearn.model_selection import GridSearchCV, train_test_split, TimeSeriesSplit, cross_val_score, StratifiedKFold
from sklearn.metrics import confusion_matrix, RocCurveDisplay, f1_score, max_error, roc_curve, auc
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, precision_score, recall_score, roc_auc_score, root_mean_squared_error,r2_score, PredictionErrorDisplay, mean_absolute_error, median_absolute_error
from sklearn.compose import TransformedTargetRegressor, ColumnTransformer
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
df_daily = df_daily.rename(columns={"high_proportion_of_day": "high_proportion_of_interval", "low_proportion_of_day": "low_proportion_of_interval"}) 

## 4 Hourly:
df_4hourly = loadDataSet(instrument, 'H4')

## Hourly:
df_hourly = loadDataSet(instrument, 'H1')

## M15:
df_m15 = loadDataSet(instrument, 'M15')

## M5:
df_m5 = loadDataSet(instrument, 'M5')

## M1:
df_m1 = loadDataSet(instrument, 'M1')

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

def create_shifted_columns(df, columns, shift_count, drop_na=False):
    
    x=shift_count +1
    new_columns = []
    
    for i in range(1,x):
        new_df_tmp = pd.concat([add_shifted_column(df, c, i) for c in columns], axis=1)
        df = pd.concat([df,  new_df_tmp], axis=1)
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

def create_RF_CLF_GridSearch(intervals_lookback, preprocessorRF=None, param_grid=None):
    tscv = TimeSeriesSplit(n_splits=5, gap=(intervals_lookback*2)+1)
    clf = RandomForestClassifier(random_state=0) #, class_weight='balanced_subsample')
    if preprocessorRF is None:
        preprocessorRF = ColumnTransformer(
            transformers=[
            # ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
            # ('num', Pipeline([
            #             ("standardScaler",  StandardScaler()), #PowerTransformer()),
            #             # ("quantiles", QuantileTransformer(n_quantiles=50, output_distribution="normal")),
            #             # ("Kbins", KBinsDiscretizer(n_bins=20, encode="ordinal") )
            #     ]), numeric_features),#StandardScaler(), numeric_features)
            ],
            remainder='passthrough',  # This keeps the remaining columns (numeric) as they are
            verbose_feature_names_out=False
        )

    # Create the full pipeline
    pipelineRF = Pipeline(steps=[
        ('preprocessor', preprocessorRF),  # Apply the preprocessor
        ('classifier', clf)        # Apply the RF model
    ])

    # Define hyperparameters to tune during cross-validation
    if param_grid is None:
        param_grid = {
        'classifier__n_estimators': [300],  # Number of trees
        'classifier__max_depth': [20, 50],  # Maximum depth of trees
        'classifier__max_features': ['log2'],
        'classifier__min_samples_leaf': [1, 4],
        'classifier__min_samples_split': [2, 10],
        }
        
    grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
    return grid_search

def runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols, label=None):
    if label is None:
        d = date.today()
        label = d.strftime("%y_%d_%m")
    set_config(transform_output="pandas")
    
    run = neptune.init_run( 
    name=f'RF Grid Search {label}',  # optional
    tags=["RandomForestClassifier", "classification"],  # optional
    project=PROJECT, api_token=API_TOKEN
    )
    # Fit the model using grid search with cross-validation
    grid_search.fit(x_train, y_train)
    
 
    
    # Find the best parameters from cross-validation
    print(f"Best Parameters: {grid_search.best_params_}")
    print(f"Best Score: {grid_search.best_score_}")
        
    # Predict and evaluate the model on the test set using the best model
    clf = grid_search.best_estimator_['classifier']
    feature_names = clf.feature_names_in_

    os.makedirs(MODEL_FOLDER, exist_ok=True)
    filename = os.path.join(MODEL_FOLDER, f'rf_model_{label}_{int(time.time())}.sav')
     
    joblib.dump(clf, filename)
    
    # load the model from disk
    clf = joblib.load(filename)
    
    # see if there has been a reduction in features (Recursive Feature Elimination or PCA)
     # x_train.columns.values.tolist()# [i for i in x_train.columns.values]
    print(f'Num Features at start of Pipeline:{len(feature_cols)}, Num after GridSearch: {len(feature_names)}')
    x_test = x_test[feature_names]
    
    run["clf_summary"] = npt_utils.create_classifier_summary(
        clf, x_train, x_test, y_train, y_test
    )

    y_pred = clf.predict(x_test)
    y_pred_proba = clf.predict_proba(x_test)

    y_true = y_test

    scores = {
            "ROC 0": f"{roc_auc_score(y_true, y_pred_proba[:,0], multi_class='ovr'):.3f}",
            "ROC 1": f"{roc_auc_score(y_true, y_pred_proba[:,1], multi_class='ovr'):.3f}",
            "F1": f"{f1_score(y_true, y_pred):.3f}",
            "Accuracy": f"{accuracy_score(y_true, y_pred):.3f}",
            "Precision": f"{precision_score(y_true, y_pred, average='weighted', zero_division=np.nan):.3f}",
            "Recall": f"{recall_score(y_test, y_pred, average='weighted'):.3f}"
        }

    print(scores)
    
    run["scores/ROC_0"] = scores['ROC 0']
    run["scores/ROC_1"] = scores['ROC 1']
    run["scores/F1"] = scores['F1']
    run["scores/Accuracy"] = scores['Accuracy']
    run["scores/Precision"] = scores['Precision']
    run["scores/Recall"] = scores['Recall']
    
    
    cm = confusion_matrix(y_test, y_pred, normalize='all')
    ConfusionMatrixDisplay.from_predictions(y_test, y_pred) #, normalize='all')
    fig, ax = plt.subplots (figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='.2f', linewidths=.3)
    plt.show ()
    run["plots/matplotlib-ConfusionMatrixDisplay"].upload(fig)


    plt.figure(figsize=(40,40))
    fig, _ = plt.subplots(1, 1, figsize=(15, 25))
    importances = clf.feature_importances_
    df3=pd.DataFrame({'allvarlist':feature_names,'importances':importances})
    df3.sort_values('importances',inplace=True)
    df3t = df3.iloc[df3.shape[0] - 40:]
    plt.barh(df3t.allvarlist,df3t.importances)
    plt.show()
    run["plots/matplotlib-FeatureImportances-top40"].upload(fig)

    g = sns.displot(kind='hist', x=y_true, height=3, bins=100)
    run["plots/seaborn-y_true_hist"].upload(g)

    g = sns.displot(kind='hist', x=y_pred, height=3, bins=100)
    run["plots/seaborn-y_pred_hist"].upload(g)

    # RocCurveDisplay.from_predictions( y_test, y_pred)

    # roc Curve plot
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba[:,1])
    roc_auc = auc(fpr, tpr)

    # Plot ROC curve
    fig = plt.figure(figsize=(10, 8), dpi = 600)
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'{label} Nas100USD Direction –– ROC Curve')
    plt.legend(loc="lower right")
    plt.show()
    run["plots/matplotlib-ROC_curve"].upload(fig)
    
    from sklearn.metrics import precision_recall_curve, PrecisionRecallDisplay
    # fig = plt.figure(figsize=(10, 8), dpi = 600)
    display = PrecisionRecallDisplay.from_predictions(
        y_test, y_pred_proba[:,1], name=label, plot_chance_level=True
    )
    _ = display.ax_.set_title("2-class Precision-Recall curve") 
    fig = display.figure_
    run["plots/matplotlib-PrecisionRecallDisplay"].upload(fig)

    run.stop()
    
    return clf

def performGrid(pipeline, param_grid, X_train, y_train, X_test, label=None):
    if label is None:
        d = date.today()
        label = d.strftime("%y-%d-%m")
    # Perform GridSearchCV with 5-fold cross-validation
    # grid_search = GridSearchCV(pipeline, param_grid, cv=5, scoring='accuracy')
    grid_search = GridSearchCV(pipeline, param_grid, cv=5, scoring='roc_auc_ovr', verbose=2) #,n_jobs=-4
    
    # Fit the model using grid search with cross-validation
    grid_search.fit(X_train, y_train)
    # grid_search.fit(X_train, y_train, classifier__eval_set=eval_set)
    
    # Find the best parameters from cross-validation
    print(f"Best Parameters: {grid_search.best_params_}")
    print(f"Best Score: {grid_search.best_score_}")
    
    # Predict and evaluate the model on the test set using the best model
    xgb_model = grid_search.best_estimator_['classifier']
    xgb_model.save_model(f'ohlc_reg_model_{label}.json')
    y_pred = xgb_model.predict(X_test)
    y_pred_prob = xgb_model.predict_proba(X_test)

    y_pred_prob = xgb_model.predict_proba(X_test)
    roc = roc_auc_score(y_test, y_pred_prob, multi_class='ovr')
    print(f"Test ROC: {roc}")
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Test Accuracy: {accuracy}")
    df_cv_results = pd.DataFrame.from_dict(grid_search.cv_results_)
    
    from sklearn.metrics import confusion_matrix, RocCurveDisplay
    cm = confusion_matrix(y_test, y_pred, normalize='all')
    # confusionMatrixDisplay.from_predictions(y_test, y_pred, normalize='all')
    fig, ax = plt.subplots (figsize=(15, 15))
    sns.heatmap(cm, annot=True, fmt='.2f', linewidths=.3)
    plt.show ()

    # RocCurveDisplay.from_predictions( y_test, y_pred_prob)
    
    from lime.lime_tabular import LimeTabularExplainer
    i = np.random.randint(0, X_test.shape[0])
    # categorical_names = grid_search.best_estimator_['preprocessor']['cat'].feature_names_in_
    # categorical_names
    categorical_names = {}
    for feature in categorical_features:
        le = le = LabelEncoder() #grid_search.best_estimator_['preprocessor']['cat']
        le.fit(X_train[feature])
        categorical_names[feature] = le.classes_
        
    explainer = LimeTabularExplainer(X_train.values, feature_names=feature_cols, class_names=np.unique(y_train),  categorical_features=categorical_features, 
                                                       categorical_names=categorical_names, discretize_continuous=True)
    exp = explainer.explain_instance(X_test.values[i], xgb_model.predict_proba, num_features=10)
    exp.show_in_notebook(show_table=True)
    return xgb_model

def performGrid_r(pipeline, param_grid, X_train, y_train, X_test, label=None):
    if label is None:
        d = date.today()
        label = d.strftime("%y-%d-%m")
    # Perform GridSearchCV with 5-fold cross-validation
    # grid_search = GridSearchCV(pipeline, param_grid, cv=5, scoring='accuracy')
    grid_search = GridSearchCV(pipeline, param_grid, cv=5, scoring='neg_root_mean_squared_error', verbose=2) #,n_jobs=-4 'neg_mean_absolute_error'
    
    # Fit the model using grid search with cross-validation
    grid_search.fit(X_train, y_train)
    # grid_search.fit(X_train, y_train, classifier__eval_set=eval_set)
    
    # Find the best parameters from cross-validation
    print(f"Best Parameters: {grid_search.best_params_}")
    print(f"Best Score: {grid_search.best_score_}")
    
    # Predict and evaluate the model on the test set using the best model
    xgb_model = grid_search.best_estimator_['regressor']
    xgb_model.save_model(f'ohlc_reg_model_{label}.json')
    y_pred = xgb_model.predict(X_test)

    # StandardScaler()
    rmse = root_mean_squared_error(y_test, y_pred)
    print(f"Test RMSE: {rmse}")
    r2 = r2_score(y_test, y_pred)
    print(f"Test R2: {r2}")
    mae = mean_absolute_error(y_test, y_pred)
    print(f"Test mae: {mae}")
    
    disp = PredictionErrorDisplay.from_predictions(y_true=y_test, y_pred=y_pred)
    plt.show()

    disp = PredictionErrorDisplay.from_predictions(y_true=y_test, y_pred=y_pred, kind='actual_vs_predicted')
    plt.show()
    
    
    return xgb_model

def compute_score(y_true, y_pred):
    return {
        "R2": f"{r2_score(y_true, y_pred):.3f}",
        "MedAE": f"{median_absolute_error(y_true, y_pred):.3f}",
        "MAE": f"{mean_absolute_error(y_true, y_pred):.3f}",
        "RSME": f"{root_mean_squared_error(y_test, y_pred):.3f}"
    }
    
def compute_score_clf(y_true, y_pred):
    return {
        "ROC": f"{roc_auc_score(y_true, y_pred, multi_class='ovr'):.3f}",
        "Accuracy": f"{accuracy_score(y_true, y_pred):.3f}",
        "Precision": f"{precision_score(y_true, y_pred):.3f}",
        "Recall": f"{recall_score(y_test, y_pred):.3f}"
    }

def show_model_perf(y_true, y_pred, label):
    f, (ax0, ax1) = plt.subplots(1, 2, figsize=(8, 4))
    
    PredictionErrorDisplay.from_predictions(y_true=y_true, y_pred=y_pred, kind='actual_vs_predicted', ax=ax0, scatter_kwargs={"alpha": 0.5})
    PredictionErrorDisplay.from_predictions(y_true=y_true, y_pred=y_pred, ax=ax1, scatter_kwargs={"alpha": 0.5})
    for name, score in compute_score(y_true, y_pred).items():
        ax0.plot([], [], " ", label=f"{name}={score}")
    ax0.legend(loc="upper left")
    ax0.set_title(f'{label} regression')
    ax1.set_title(f'{label} residuals')
    plt.show()
    
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

#%% Test Train Data Split
intervals_lookback = 5

target_col = 'low_proportion_of_interval'#'interval_return' #'high_proportion_of_day'#'high_hour_of_day' #'bullish' #'high_hour_of_day' # Colud be any of the End of Periood Columns

x_test, x_train, y_test, y_train, categorical_features, numeric_features = getFeatureEngineeredTestTrainData(df_daily, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)

feature_cols = categorical_features + numeric_features
#%% Gaussian Mixture Model Exploration
from sklearn.mixture import GaussianMixture
gmm = GaussianMixture(n_components=3, random_state=42)
gmm.fit(y_train.values.reshape(-1, 1))
temp_df = pd.DataFrame()
temp_df['target'] = y_train
temp_df['target_class'] = gmm.predict(y_train.values.reshape(-1, 1))


f, ax = plt.subplots(nrows=1, ncols=3, figsize=(18, 6))
sns.kdeplot(data=y_train, ax=ax[0], bw_adjust=.1)
ax[0].set_title('Before GMM', fontsize=16)
sns.histplot(x=temp_df[temp_df.target_class==0].target,  bins=20, ax=ax[1], alpha=0.2)
sns.histplot(x=temp_df[temp_df.target_class==1].target,  bins=20, ax=ax[1], alpha=0.2)
sns.histplot(x=temp_df[temp_df.target_class==2].target,  bins=20, ax=ax[1], alpha=0.2)
sns.kdeplot(data=temp_df[temp_df.target_class==0].target, label='Component 1', ax=ax[2], bw_adjust=.1)
sns.kdeplot(data=temp_df[temp_df.target_class==1].target, label='Component 2', ax=ax[2], bw_adjust=.1)
sns.kdeplot(data=temp_df[temp_df.target_class==2].target, label='Component 3', ax=ax[2], bw_adjust=.1)
sns.kdeplot(data=temp_df[temp_df.target_class==3].target, label='Component 4', ax=ax[2], bw_adjust=.1)
sns.histplot(x=y_test,  bins=20, ax=ax[0].twinx(),alpha=0.2)

ax[1].set_title('After GMM', fontsize=16)
plt.show()


#%% Preprocessing and Pipeline
# Create the column transformer to apply OneHotEncoder to the categorical columns
 # ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features),
preprocessor = ColumnTransformer(
    transformers=[
        ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
        ('num', StandardScaler(), numeric_features) 
    ],
    remainder='passthrough'  # This keeps the remaining columns (numeric) as they are
)

preprocessor_r = ColumnTransformer(
    transformers=[
        ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
        ('num', 
         Pipeline([
                    ("standardScaler",  PowerTransformer()),
                    ("quantiles", QuantileTransformer(n_quantiles=50, output_distribution="normal")),
                    # ("Kbins", KBinsDiscretizer(n_bins=4, encode="ordinal") )
            ]), numeric_features),#StandardScaler(), numeric_features) 
    ],
    remainder='passthrough'  # This keeps the remaining columns (numeric) as they are
)

# Define the XGBoost model (use XGBClassifier for classification)
xgb_model = XGBClassifier(
    # use_label_encoder=False,  # Important for newer XGBoost versions
    verbosity=1,              # Set verbosity level to INFO (2) to see more details
    tree_method = "hist",    # Use GPU for training
    device = "cuda",
    eval_metric='auc', #'logloss',     # Prevent warning with classification metrics
    learning_rate =0.008, n_estimators=60, max_depth=5, min_child_weight=3, 
    # gamma=0,
    # colsample_bytree=0.6, subsample=0.6,
    nthread=4, 
    seed=27
)

xgb_model_r = XGBRegressor(
    verbosity=1,              # Set verbosity level to INFO (2) to see more details
    tree_method = "hist",    # Use GPU for training
    device = "cuda",
    learning_rate =0.1, n_estimators=10000, max_depth=20, min_child_weight=3,
    nthread=4, 
    seed=27)

# Create the full pipeline
pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),  # Apply the preprocessor
    ('classifier', xgb_model)        # Apply the XGBoost model
])

pipeline_r = Pipeline(steps=[
    ('preprocessor', preprocessor_r),  # Apply the preprocessor
    # ('PCA_red', PCA(n_components=10)),
    ('regressor', xgb_model_r)        # Apply the XGBoost model
])

# Define hyperparameters to tune during cross-validation
param_grid = {
    'classifier__n_estimators': [59, 60, 61],  # Number of trees
    'classifier__learning_rate': [0.0077, 0.008, 0.0082],  # Learning rate
    # 'classifier__max_depth': [2, 3, 4, 5],  # Maximum depth of trees
    # 'classifier__min_child_weight':range(1,6,2)
}

param_grid_r = {
    'regressor__n_estimators': [50, 100, 200],  # Number of trees
    'regressor__learning_rate': [0.01, 0.015, 0.02],  # Learning rate
    # 'classifier__max_depth': [2, 3, 4, 5],  # Maximum depth of trees
    # 'classifier__min_child_weight':range(1,6,2)
}

#%% Execute Model
# Feature Scaling Pipeline and Target Variable Transformation
xgb_model_r_with_trans_target = TransformedTargetRegressor(
    regressor=pipeline_r,
    transformer=QuantileTransformer(n_quantiles=50, output_distribution="normal"),
).fit(x_train, y_train)

y_pred_xgb_model_r_with_trans_target = xgb_model_r_with_trans_target.predict(x_test)

y_trans = quantile_transform(
    y_train.to_frame(), n_quantiles=900, output_distribution="normal", copy=True
).squeeze()

g = sns.displot(kind='hist', x=y_test, height=3, bins=100)
# g = sns.displot(kind='hist', x=y_trans, height=3, bins=100)
# g = sns.displot(kind='hist', x=y_pred, height=3, bins=100)
g = sns.displot(kind='hist', x=y_pred_xgb_model_r_with_trans_target, height=3, bins=100)

# show_model_perf(y_true=y_test, y_pred=y_pred_no_scale, label='No Feature Scale')
# show_model_perf(y_true=y_test, y_pred=y_pred, label='No Target Trans')
show_model_perf(y_true=y_test, y_pred=y_pred_xgb_model_r_with_trans_target, label='With Target Trans')

### Feature Importnances:
    
plt.figure(figsize=(40,40))
plt.subplots(1, 1, figsize=(20, 15))
importances = xgb_model_r_with_trans_target.regressor_['regressor'].feature_importances_
df3=pd.DataFrame({'allvarlist':feature_cols,'importances':importances})
df3.sort_values('importances',inplace=True)
plt.barh(df3.allvarlist,df3.importances)
plt.show()

from xgboost import plot_importance
plot_importance(xgb_model_r_with_trans_target.regressor_['regressor'], importance_type='gain')
plt.show()


### Lime Explainer:
# from lime.lime_tabular import LimeTabularExplainer
# i = np.random.randint(0, X_test.shape[0])
# # categorical_names = grid_search.best_estimator_['preprocessor']['cat'].feature_names_in_
# # categorical_names
# categorical_names = {}
# for feature in categorical_features:
#     le = le = LabelEncoder() #grid_search.best_estimator_['preprocessor']['cat']
#     le.fit(X_train[feature])
#     categorical_names[feature] = le.classes_

# # categorical_names
    
# explainer = LimeTabularExplainer(X_train.values, feature_names=feature_cols, class_names=np.unique(y_train),  categorical_features=categorical_features, 
#                                                    categorical_names=categorical_names, discretize_continuous=True)
# exp = explainer.explain_instance(X_test.values[i], xgb_model.predict_proba, num_features=10)
# exp.show_in_notebook(show_table=True)
#%% Random Forest - Multi Output Classification 
setup_Neptune()
intervals_lookback = 1
target_col = 'bullish' #'high_hour_of_day'#'interval_return' #'high_proportion_of_day'#'high_hour_of_day' #'bullish' #'high_hour_of_day' # Colud be any of the End of Periood Columns

x_test, x_train, y_test, y_train, categorical_features, numeric_features = getFeatureEngineeredTestTrainData(df_daily, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)

preprocessorRF = ColumnTransformer(
    transformers=[
        # ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
        # ('num', Pipeline([
        #             ("standardScaler",  StandardScaler()), #PowerTransformer()),
        #             # ("quantiles", QuantileTransformer(n_quantiles=50, output_distribution="normal")),
        #             # ("Kbins", KBinsDiscretizer(n_bins=20, encode="ordinal") )
        #     ]), numeric_features),#StandardScaler(), numeric_features)
    ],
    remainder='passthrough',  # This keeps the remaining columns (numeric) as they are
    verbose_feature_names_out=False
)

# Define hyperparameters to tune during cross-validation
param_grid = {
    'classifier__n_estimators': [800, 1100],  # Number of trees
    # 'classifier__learning_rate': [0.0077, 0.008, 0.0082],  # Learning rate
    'classifier__max_depth': [15, 30],  # Maximum depth of trees
    'classifier__max_features': ['log2'],
    'classifier__min_samples_leaf': [1, 2],
    'classifier__min_samples_split': [14, 20],
    # 'classifier__min_child_weight':range(1,6,2)
}

feature_cols = categorical_features + numeric_features


# grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) 
# clf =  grid_search.fit(x_train, y_train)    

grid_search = create_RF_CLF_GridSearch(intervals_lookback, preprocessorRF, param_grid)   
clf = runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols)    
    
from sklearn.feature_selection import RFE, RFECV

tscv = TimeSeriesSplit(n_splits=5, gap=intervals_lookback+1)
rfe = RFECV(estimator=RandomForestClassifier(), cv=tscv, scoring='f1', n_jobs=-2, step=0.05)
# clf = RandomForestClassifier(random_state=0)
pipelineRF = Pipeline(steps=[
        ('rfe', rfe),  # Apply the preprocessor
        ('classifier', clf)        # Apply the RF model
    ])

param_grid = {
        'classifier__n_estimators': [300],  # Number of trees
        'classifier__max_depth': [30],  # Maximum depth of trees
        'classifier__max_features': ['log2'],
        'classifier__min_samples_leaf': [4],
        'classifier__min_samples_split': [10],
        }
 #, class_weight='balanced_subsample')

grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
clf = runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols, label='Hourly Run rfe')    


cv_results = pd.DataFrame(grid_search.best_estimator_['rfe'].cv_results_)
# # grid_search.best_estimator_['classifier'].get_feature_names_out()
# num_best_features = grid_search.best_estimator_['rfe'].get_feature_names_out().shape

best_features = grid_search.best_estimator_['rfe'].get_feature_names_out()
cv_results = cv_results.sort_values('mean_test_score', ascending=False)
plt.figure()


plt.xlabel("Number of features selected")
plt.ylabel("Mean test accuracy")
plt.errorbar(
    x=cv_results["n_features"],
    y=cv_results["mean_test_score"],
    yerr=cv_results["std_test_score"],
)
plt.title("Recursive Feature Elimination \nwith correlated features")
plt.show()

print(cv_results)
 
pipelineRF = Pipeline(steps=[
        ('classifier', clf)        # Apply the RF model
    ])

param_grid = {
        'classifier__n_estimators': [1000, 5000, 10000],  # Number of trees
        'classifier__max_depth': [30, 40],  # Maximum depth of trees
        'classifier__max_features': ['log2'],
        'classifier__min_samples_leaf': [4],
        'classifier__min_samples_split': [10],
        }
 #, class_weight='balanced_subsample')

grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
clf = runRFGridSearch(grid_search, x_train[best_features], y_train, x_test[best_features], y_test, feature_cols, label='Daily rfe test')
###
# Best Set up so far:
#     When Classifying 'high_hour_of_day':
#         Random Forest - Scoring Metric roc: grid_search = GridSearchCV(clf, param_grid, cv=StratifiedKFold(n_splits=5), scoring='roc_auc_ovo_weighted', verbose=2)
#         Best Parameters: {'max_depth': 20, 'n_estimators': 250}
#         Best Score: 0.5227422710540904
#         {'ROC': '0.545', 'Accuracy': '0.159', 'Precision': '0.148', 'Recall': '0.159'}
#         Features include 5 prior days of shifted features.
#%% Hourly

intervals_lookback = 23

target_col = 'bullish' #'low_proportion_of_interval'#'interval_return' #'high_proportion_of_day'#'high_hour_of_day' #'bullish' #'high_hour_of_day' # Colud be any of the End of Periood Columns

x_test, x_train, y_test, y_train, categorical_features, numeric_features = getFeatureEngineeredTestTrainData(df_hourly, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)

preprocessorRF = ColumnTransformer(
    transformers=[
        # ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
        # ('num', StandardScaler(), numeric_features) 
    ],
    remainder='passthrough'  # This keeps the remaining columns (numeric) as they are
)

# Define hyperparameters to tune during cross-validation
param_grid = {
    'classifier__n_estimators': [250, 275, 300],  # Number of trees
    # 'classifier__learning_rate': [0.0077, 0.008, 0.0082],  # Learning rate
    'classifier__max_depth': [20, 25, 30, 35],  # Maximum depth of trees
    # 'classifier__min_child_weight':range(1,6,2)
}

feature_cols = categorical_features + numeric_features

grid_search = create_RF_CLF_GridSearch(intervals_lookback, preprocessorRF, param_grid)
    
clf = runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols, label='Hourly Run 1')    

# %%

from sklearn.feature_selection import RFE, RFECV
rfe = RFECV(estimator=RandomForestClassifier())
tscv = TimeSeriesSplit(n_splits=5, gap=intervals_lookback+1)
clf = RandomForestClassifier(random_state=0)
pipelineRF = Pipeline(steps=[
        ('rfe', rfe),  # Apply the preprocessor
        ('classifier', clf)        # Apply the RF model
    ])

param_grid = {
        'classifier__n_estimators': [300],  # Number of trees
        'classifier__max_depth': [30],  # Maximum depth of trees
        'classifier__max_features': ['log2', 10],
        'classifier__min_samples_leaf': [4],
        'classifier__min_samples_split': [10],
        }
 #, class_weight='balanced_subsample')

grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
clf = runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols, label='Hourly Run rfe')    

cv_results = pd.DataFrame(grid_search.best_estimator_['rfe'].cv_results_)
# grid_search.best_estimator_['classifier'].get_feature_names_out()
num_best_features = grid_search.best_estimator_['rfe'].get_feature_names_out().shape

best_features = grid_search.best_estimator_['rfe'].get_feature_names_out()
cv_results = cv_results.sort_values('mean_test_score', ascending=False)
plt.figure()


plt.xlabel("Number of features selected")
plt.ylabel("Mean test accuracy")
plt.errorbar(
    x=cv_results["n_features"],
    y=cv_results["mean_test_score"],
    yerr=cv_results["std_test_score"],
)
plt.title("Recursive Feature Elimination \nwith correlated features")
plt.show()
cv_results

grid_search.best_estimator_['classifier'].n_features_in_ #feature_names_in_
# clf.n_features_in_

pipelineRF = Pipeline(steps=[
        ('classifier', clf)        # Apply the RF model
    ])

param_grid = {
        'classifier__n_estimators': [1000, 5000, 10000],  # Number of trees
        'classifier__max_depth': [30, 40],  # Maximum depth of trees
        'classifier__max_features': ['log2'],
        'classifier__min_samples_leaf': [4],
        'classifier__min_samples_split': [10],
        }
 #, class_weight='balanced_subsample')

grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
clf = runRFGridSearch(grid_search, x_train[best_features], y_train, x_test[best_features], y_test, feature_cols, label='Daily rfe test')  

#%% RFE CV Plot
cv_results = pd.DataFrame(grid_search.best_estimator_['rfe'].cv_results_)
# grid_search.best_estimator_['classifier'].get_feature_names_out()
num_best_features = grid_search.best_estimator_['rfe'].get_feature_names_out().shape

best_features = grid_search.best_estimator_['rfe'].get_feature_names_out()
cv_results = cv_results.sort_values('mean_test_score', ascending=False)
plt.figure()


plt.xlabel("Number of features selected")
plt.ylabel("Mean test accuracy")
plt.errorbar(
    x=cv_results["n_features"],
    y=cv_results["mean_test_score"],
    yerr=cv_results["std_test_score"],
)
plt.title("Recursive Feature Elimination \nwith correlated features")
plt.show()
cv_results

grid_search.best_estimator_['classifier'].n_features_in_ #feature_names_in_
# clf.n_features_in_

pipelineRF = Pipeline(steps=[
        ('classifier', clf)        # Apply the RF model
    ])

param_grid = {
        'classifier__n_estimators': [1000, 5000, 10000],  # Number of trees
        'classifier__max_depth': [30, 40],  # Maximum depth of trees
        'classifier__max_features': ['log2'],
        'classifier__min_samples_leaf': [4],
        'classifier__min_samples_split': [10],
        }
 #, class_weight='balanced_subsample')

grid_search = GridSearchCV(pipelineRF, param_grid, cv=tscv, scoring='f1', verbose=2, n_jobs=-2) # roc_auc,n_jobs=-4 'neg_mean_absolute_error' roc_auc_ovo_weighted f1
clf = runRFGridSearch(grid_search, x_train[best_features], y_train, x_test[best_features], y_test, feature_cols, label='Daily rfe test')   
#%% Stumpy
%matplotlib inline

import pandas as pd
import stumpy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib.patches import Rectangle
import datetime as dt

plt.style.use('https://raw.githubusercontent.com/TDAmeritrade/stumpy/main/docs/stumpy.mplstyle')

steam_df = pd.read_csv("https://zenodo.org/record/4273921/files/STUMPY_Basics_steamgen.csv?download=1")
steam_df.head()

plt.suptitle('Steamgen Dataset', fontsize='30')
plt.xlabel('Time', fontsize ='20')
plt.ylabel('Steam Flow', fontsize='20')
plt.plot(steam_df['steam flow'].values)
plt.show()

m = 640
fig, axs = plt.subplots(2)
plt.suptitle('Steamgen Dataset', fontsize='30')
axs[0].set_ylabel("Steam Flow", fontsize='20')
axs[0].plot(steam_df['steam flow'], alpha=0.5, linewidth=1)
axs[0].plot(steam_df['steam flow'].iloc[643:643+m])
axs[0].plot(steam_df['steam flow'].iloc[8724:8724+m])
rect = Rectangle((643, 0), m, 40, facecolor='lightgrey')
axs[0].add_patch(rect)
rect = Rectangle((8724, 0), m, 40, facecolor='lightgrey')
axs[0].add_patch(rect)
axs[1].set_xlabel("Time", fontsize='20')
axs[1].set_ylabel("Steam Flow", fontsize='20')
axs[1].plot(steam_df['steam flow'].values[643:643+m], color='C1')
axs[1].plot(steam_df['steam flow'].values[8724:8724+m], color='C2')
plt.show()


motif_idx = np.argsort(mp[:, 0])[0]

print(f"The motif is located at index {motif_idx}")


nearest_neighbor_idx = mp[motif_idx, 1]

print(f"The nearest neighbor is located at index {nearest_neighbor_idx}")


fig, axs = plt.subplots(2, sharex=True, gridspec_kw={'hspace': 0})
plt.suptitle('Motif (Pattern) Discovery', fontsize='30')

axs[0].plot(steam_df['steam flow'].values)
axs[0].set_ylabel('Steam Flow', fontsize='20')
rect = Rectangle((motif_idx, 0), m, 40, facecolor='lightgrey')
axs[0].add_patch(rect)
rect = Rectangle((nearest_neighbor_idx, 0), m, 40, facecolor='lightgrey')
axs[0].add_patch(rect)
axs[1].set_xlabel('Time', fontsize ='20')
axs[1].set_ylabel('Matrix Profile', fontsize='20')
axs[1].axvline(x=motif_idx, linestyle="dashed")
axs[1].axvline(x=nearest_neighbor_idx, linestyle="dashed")
axs[1].plot(mp[:, 0])
plt.show()

mp = stumpy.gpu_stump(df['value'], m=m)  # Note that you'll need a properly configured NVIDIA GPU for this


#%% Prediciton of Trained RF Model

# x_test.shape, x_train.shape, y_test.shape, y_train.shape, len(feature_cols)
# cols = x_test.columns.values.tolist()
# cols.sort()
# print(cols)
label='Daily rfe test'
feature_names = x_train.columns.values.tolist()# [i for i in x_train.columns.values]
print(f'Num Features at start of Pipeline:{len(feature_cols)}, Num after GridSearch: {len(feature_names)}')

y_pred = clf.predict(x_test[feature_names])
y_pred_proba = clf.predict_proba(x_test[feature_names])

y_true = y_test

scores = {
        "ROC 0": f"{roc_auc_score(y_true, y_pred_proba[:,0], multi_class='ovr'):.3f}",
        "ROC 1": f"{roc_auc_score(y_true, y_pred_proba[:,1], multi_class='ovr'):.3f}",
        "Accuracy": f"{accuracy_score(y_true, y_pred):.3f}",
        "Precision": f"{precision_score(y_true, y_pred, average='weighted', zero_division=np.nan):.3f}",
        "Recall": f"{recall_score(y_test, y_pred, average='weighted'):.3f}"
    }

print(scores)

cm = confusion_matrix(y_test, y_pred, normalize='all')
ConfusionMatrixDisplay.from_predictions(y_test, y_pred) #, normalize='all')
fig, ax = plt.subplots (figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt='.2f', linewidths=.3)
plt.show ()


plt.figure(figsize=(40,40))
plt.subplots(1, 1, figsize=(15, 25))
importances = clf.feature_importances_
df3=pd.DataFrame({'allvarlist':feature_names,'importances':importances})
df3.sort_values('importances',inplace=True)
df3t = df3.iloc[df3.shape[0] - 40:]
plt.barh(df3t.allvarlist,df3t.importances)
plt.show()

g = sns.displot(kind='hist', x=y_true, height=3, bins=100)
g = sns.displot(kind='hist', x=y_pred, height=3, bins=100)
# RocCurveDisplay.from_predictions( y_test, y_pred)

# roc Curve plot
fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba[:,1])
roc_auc = auc(fpr, tpr)

# Plot ROC curve
plt.figure(figsize=(10, 8), dpi = 600)
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title(f'{label} Nas100USD Direction –– ROC Curve')
plt.legend(loc="lower right")
plt.show()

from sklearn.metrics import precision_recall_curve, PrecisionRecallDisplay

display = PrecisionRecallDisplay.from_predictions(
    y_test, y_pred_proba[:,1], name=label, plot_chance_level=True
)
_ = display.ax_.set_title("2-class Precision-Recall curve") 
# %%
#%% RFE Classifier to use
# get a list of models to evaluate
def get_models(baseModel, rfeCV):
	models = dict()
	# lr
	rfeCV.estimator=LogisticRegression()
	model = baseModel
	models['lr'] = Pipeline(steps=[('s',rfeCV),('m',model)])
	# perceptron
	rfeCV.estimator=Perceptron()
	model = baseModel
	models['per'] = Pipeline(steps=[('s',rfeCV),('m',model)])
	# cart
	rfeCV.estimator=DecisionTreeClassifier()
	model = baseModel
	models['cart'] = Pipeline(steps=[('s',rfeCV),('m',model)])
	# rf
	rfeCV.estimator=RandomForestClassifier()
	model = baseModel
	models['rf'] = Pipeline(steps=[('s',rfeCV),('m',model)])
	# gbm
	rfeCV.estimator=GradientBoostingClassifier()
	model = baseModel
	models['gbm'] = Pipeline(steps=[('s',rfeCV),('m',model)])
	return models

# evaluate a give model using cross-validation
def evaluate_model(model, X, y):
	cv = TimeSeriesSplit(n_splits=5, gap=intervals_lookback+1)
	scores = cross_val_score(model, X, y, scoring='accuracy', cv=cv, n_jobs=-2)
	return scores


intervals_lookback = 1
target_col = 'bullish' #'high_hour_of_day'#'interval_return' #'high_proportion_of_day'#'high_hour_of_day' #'bullish' #'high_hour_of_day' # Colud be any of the End of Periood Columns

x_test, x_train, y_test, y_train, categorical_features, numeric_features = getFeatureEngineeredTestTrainData(df_daily, descriptive_cols, end_of_period_num_cols, end_of_period_cat_cols, target_col, intervals_lookback)

preprocessorRF = ColumnTransformer(
    transformers=[
        # ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=np.nan), categorical_features),
        # ('num', Pipeline([
        #             ("standardScaler",  StandardScaler()), #PowerTransformer()),
        #             # ("quantiles", QuantileTransformer(n_quantiles=50, output_distribution="normal")),
        #             # ("Kbins", KBinsDiscretizer(n_bins=20, encode="ordinal") )
        #     ]), numeric_features),#StandardScaler(), numeric_features)
    ],
    remainder='passthrough',  # This keeps the remaining columns (numeric) as they are
    verbose_feature_names_out=False
)

# Define hyperparameters to tune during cross-validation
param_grid = {
    'classifier__n_estimators': [925, 975],  # Number of trees
    # 'classifier__learning_rate': [0.0077, 0.008, 0.0082],  # Learning rate
    'classifier__max_depth': [14, 19],  # Maximum depth of trees
    'classifier__max_features': ['log2'],
    'classifier__min_samples_leaf': [2, 3],
    'classifier__min_samples_split': [14, 17],
    # 'classifier__min_child_weight':range(1,6,2)
}

feature_cols = categorical_features + numeric_features
 

grid_search = create_RF_CLF_GridSearch(intervals_lookback, preprocessorRF, param_grid)   
clf = runRFGridSearch(grid_search, x_train, y_train, x_test, y_test, feature_cols)    
    
from sklearn.feature_selection import RFE, RFECV

tscv = TimeSeriesSplit(n_splits=5, gap=intervals_lookback+1)
rfe = RFECV(estimator=RandomForestClassifier(), cv=tscv, scoring='f1', n_jobs=-2, step=0.05)

# cv_results = pd.DataFrame(grid_search.best_estimator_['rfe'].cv_results_)
# # # grid_search.best_estimator_['classifier'].get_feature_names_out()
# # num_best_features = grid_search.best_estimator_['rfe'].get_feature_names_out().shape

# best_features = grid_search.best_estimator_['rfe'].get_feature_names_out()
# cv_results = cv_results.sort_values('mean_test_score', ascending=False)
# plt.figure()


# plt.xlabel("Number of features selected")
# plt.ylabel("Mean test accuracy")
# plt.errorbar(
#     x=cv_results["n_features"],
#     y=cv_results["mean_test_score"],
#     yerr=cv_results["std_test_score"],
# )
# plt.title("Recursive Feature Elimination \nwith correlated features")
# plt.show()

# print(cv_results)
models = get_models(clf, rfe)

from numpy import mean
from numpy import std

# evaluate the models and store results
results, names = list(), list()
for name, model in models.items():
	scores = evaluate_model(model, x_train, y_train)
	results.append(scores)
	names.append(name)
	print('>%s %.3f (%.3f)' % (name, mean(scores), std(scores)))
# plot model performance for comparison
plt.pyplot.boxplot(results, labels=names, showmeans=True)
plt.pyplot.show()


#%% Neptune Scratch
from sklearn.datasets import fetch_california_housing
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
parameters = {"n_estimators": 70, "max_depth": 7, "min_samples_split": 3}

estimator = RandomForestRegressor(**parameters)
X, y = fetch_california_housing(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
)
estimator.fit(X_train, y_train)

import neptune

run = neptune.init_run(project='beats-working/NQ-Predict', api_token=API_TOKEN)

run["params"] = parameters
y_pred = estimator.predict(X_test)

run["scores/max_error"] = max_error(y_test, y_pred)
run["scores/mean_absolute_error"] = mean_absolute_error(y_test, y_pred)
run["scores/r2_score"] = r2_score(y_test, y_pred)
run.stop()

# Only Esitmator PArams:
import neptune.integrations.sklearn as npt_utils
from neptune.utils import stringify_unsupported

rfc = RandomForestClassifier()

run = neptune.init_run(name="only estimator params", project='beats-working/NQ-Predict', api_token=API_TOKEN)  # name is optional

run["estimator/params"] = stringify_unsupported(npt_utils.get_estimator_params(rfc))

run.stop()

#log pickled file:
import neptune.integrations.sklearn as npt_utils
from sklearn.datasets import load_digits

rfc = RandomForestClassifier()
X, y = load_digits(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=28743
)
rfc.fit(X, y)

run = neptune.init_run(
    name="only pickled model",  # optional
    project='beats-working/NQ-Predict', api_token=API_TOKEN
)

run["estimator/pickled-model"] = npt_utils.get_pickled_model(rfc)

run.stop()

#confuasion Matrix:
from sklearn.datasets import load_digits
import neptune.integrations.sklearn as npt_utils

rfc = RandomForestClassifier()
X, y = load_digits(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=28743
)
rfc.fit(X_train, y_train)

run = neptune.init_run(
    name="only confusion matrix",  # optional
    project='beats-working/NQ-Predict', api_token=API_TOKEN
)

run["confusion-matrix"] = npt_utils.create_confusion_matrix_chart(
    rfc, X_train, X_test, y_train, y_test
)

run.stop()

# log Classification Summary:
from sklearn.datasets import load_digits
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

parameters = {
    "n_estimators": 120,
    "learning_rate": 0.12,
    "min_samples_split": 3,
    "min_samples_leaf": 2,
}

gbc = GradientBoostingClassifier(**parameters)

X, y = load_digits(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

gbc.fit(X_train, y_train)

import neptune
import neptune.integrations.sklearn as npt_utils

setup_Neptune()

run = neptune.init_run( 
    name="classification example",  # optional
    tags=["GradientBoostingClassifier", "classification"],  # optional
    project=PROJECT, api_token=API_TOKEN
)


run["cls_summary"] = npt_utils.create_classifier_summary(
    gbc, X_train, X_test, y_train, y_test
)
run.stop()