#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 24 09:50:12 2018

@author: Kazuki
"""

import numpy as np
import pandas as pd
import os, gc
from glob import glob
from tqdm import tqdm

import sys
sys.path.append(f'/home/{os.environ.get("USER")}/PythonLibrary')
import lgbextension as ex
import lightgbm as lgb
from multiprocessing import cpu_count

import utils, utils_metric
#utils.start(__file__)
#==============================================================================



SEED = np.random.randint(9999)
np.random.seed(SEED)
print('SEED:', SEED)

NFOLD = 5

LOOP = 5

param = {
         'objective': 'multiclass',
         'num_class': 14,
         'metric': 'multi_logloss',
         
         'learning_rate': 0.5,
         'max_depth': 3,
         'num_leaves': 63,
         'max_bin': 255,
         
         'min_child_weight': 10,
         'min_data_in_leaf': 100,
         'reg_lambda': 0.5,  # L2 regularization term on weights.
         'reg_alpha': 0.5,  # L1 regularization term on weights.
         
#         'colsample_bytree': 0.5,
#         'subsample': 0.9,
#         'nthread': 32,
         'nthread': cpu_count(),
         'bagging_freq': 1,
         'verbose':-1,
         
         'seed': SEED
         }

USE_FEATURES = 500

# =============================================================================
# load
# =============================================================================
COL = pd.read_csv('LOG/imp_801_cv.py-2.csv').head(USE_FEATURES ).feature.tolist()


PREFS = sorted(set([c.split('_')[0] for c in COL]))

files_tr = []
for pref in PREFS:
    files_tr += glob(f'../data/train_{pref}*.pkl')

X = pd.concat([
                pd.read_pickle(f) for f in tqdm(files_tr, mininterval=60)
               ], axis=1)[COL]
y = utils.load_target().target

#X.drop(DROP, axis=1, inplace=True)

target_dict = {}
target_dict_r = {}
for i,e in enumerate(y.sort_values().unique()):
    target_dict[e] = i
    target_dict_r[i] = e

y = y.replace(target_dict)

if X.columns.duplicated().sum()>0:
    raise Exception(f'duplicated!: { X.columns[X.columns.duplicated()] }')
print('no dup :) ')
print(f'X.shape {X.shape}')

gc.collect()


# =============================================================================
# search param
# =============================================================================
from itertools import product

param_list = []

# colsample_bytree
for i,j in product(np.arange(0.1, 1, 0.2), np.arange(0.1, 1, 0.2)):
    param_ = param.copy()
    param_['colsample_bytree'] = round(i, 2)
    param_['subsample'] = round(j, 2)
    param_list.append(param_)


# =============================================================================
# cv
# =============================================================================

model_all = []
nround_mean = 0
wloss_list = []
y_preds = []

dtrain = lgb.Dataset(X[COL], y.values, #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()
    
for param_ in param_list:
    gc.collect()
    print(f"\ncolsample_bytree: {param_['colsample_bytree']}    subsample: {param_['subsample']}")
    ret, models = lgb.cv(param_, dtrain, 99999, nfold=NFOLD, 
                         fobj=utils_metric.wloss_objective, 
                         feval=utils_metric.wloss_metric,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    y_pred = ex.eval_oob(X[COL], y.values, models, SEED, stratified=True, shuffle=True, 
                         n_class=y.unique().shape[0])
    y_preds.append(y_pred)
    model_all += models
    nround_mean += len(ret['wloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

#nround_mean = int((nround_mean/1) * 1.3)
#
#result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
#print(result)
#
#imp = ex.getImp(model_all)
#imp['split'] /= imp['split'].max()
#imp['gain'] /= imp['gain'].max()
#imp['total'] = imp['split'] + imp['gain']
#
#imp.sort_values('total', ascending=False, inplace=True)
#imp.reset_index(drop=True, inplace=True)
#
#
#imp.to_csv(f'LOG/imp_{__file__}.csv', index=False)
#
#
## =============================================================================
## eval
## =============================================================================
#for i,y_pred in enumerate(y_preds):
#    y_pred = pd.DataFrame(utils_metric.softmax(y_pred.astype(float).values))
#    if i==0:
#        tmp = y_pred
#    else:
#        tmp += y_pred
#tmp /= len(y_preds)
#y_preds = tmp.copy().values.astype(float)
#
#
#w_score = utils_metric.multi_weighted_logloss(y.values, y_preds)
#a_score = utils_metric.akiyama_metric(y.values, y_preds)
#print(f'{w_score}    {a_score}')


#==============================================================================
#utils.end(__file__)
utils.stop_instance()
