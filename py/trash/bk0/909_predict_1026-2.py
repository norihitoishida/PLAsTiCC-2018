#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 26 16:39:11 2018

@author: kazuki.onodera
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

import utils
utils.start(__file__)
#==============================================================================

SUBMIT_FILE_PATH = '../output/1026-2.csv.gz'

COMMENT = '1026-1 + galactic cut'

EXE_SUBMIT = True

#DROP = ['f001_hostgal_photoz']

SEED = np.random.randint(9999)
np.random.seed(SEED)
print('SEED:', SEED)

NFOLD = 5

LOOP = 5

param = {
         'objective': 'multiclass',
#         'num_class': 14,
         'metric': 'multi_logloss',
         
         'learning_rate': 0.01,
         'max_depth': 6,
         'num_leaves': 63,
         'max_bin': 255,
         
         'min_child_weight': 10,
         'min_data_in_leaf': 150,
         'reg_lambda': 0.5,  # L2 regularization term on weights.
         'reg_alpha': 0.5,  # L1 regularization term on weights.
         
         'colsample_bytree': 0.5,
         'subsample': 0.5,
#         'nthread': 32,
         'nthread': cpu_count(),
         'bagging_freq': 1,
         'verbose':-1,
         }

# =============================================================================
# load
# =============================================================================

files_tr = sorted(glob('../data/train_f*.pkl'))
[print(f) for f in files_tr]

X = pd.concat([
                pd.read_pickle(f) for f in tqdm(files_tr, mininterval=60)
               ], axis=1)
y = utils.load_target().target

if X.columns.duplicated().sum()>0:
    raise Exception(f'duplicated!: { X.columns[X.columns.duplicated()] }')
print('no dup :) ')
print(f'X.shape {X.shape}')

gc.collect()


# =============================================================================
# cv(galactic)
# =============================================================================
print('==== CV galactic ====')

y_gal = y[X['f001_hostgal_photoz'] == 0]
target_dict_gal = {}
target_dict_r_gal = {}
for i,e in enumerate(y_gal.sort_values().unique()):
    target_dict_gal[e] = i
    target_dict_r_gal[i] = e

y_gal = y_gal.replace(target_dict_gal)
param['num_class'] = i+1


dtrain = lgb.Dataset(X[X['f001_hostgal_photoz'] == 0], y_gal, 
                     #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()

model_all = []
nround_mean = 0
wloss_list = []
for i in range(LOOP):
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         feval=utils.lgb_multi_weighted_logloss_gal,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    model_all += models
    nround_mean += len(ret['multi_logloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

nround_mean = int((nround_mean/LOOP) * 1.3)

result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
print(result)

imp = ex.getImp(model_all)
imp['split'] /= imp['split'].max()
imp['gain'] /= imp['gain'].max()
imp['total'] = imp['split'] + imp['gain']

imp.sort_values('total', ascending=False, inplace=True)
imp.reset_index(drop=True, inplace=True)


imp.to_csv(f'LOG/imp_{__file__}_gal.csv', index=False)

png = f'LOG/imp_{__file__}_gal.png'
utils.savefig_imp(imp, png, x='total', title=f'{__file__}_gal')
utils.send_line(result, png)


COL_gal = imp[imp.gain>0].feature.tolist()

# =============================================================================
# model(galactic)
# =============================================================================

dtrain = lgb.Dataset(X[X['f001_hostgal_photoz'] == 0], y_gal,
                     #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()


np.random.seed(SEED)

model_all = []
for i in range(LOOP):
    print('building', i)
    gc.collect()
    param['seed'] = np.random.randint(9999)
    model = lgb.train(param, dtrain, num_boost_round=nround_mean, valid_sets=None, 
                      valid_names=None, fobj=None, feval=None, init_model=None, 
                      feature_name='auto', categorical_feature='auto', 
                      early_stopping_rounds=None, evals_result=None, 
                      verbose_eval=True, learning_rates=None, 
                      keep_training_booster=False, callbacks=None)
    
    model_all.append(model)


del dtrain; gc.collect()

model_all_gal = model_all



# =============================================================================
# cv(extragalactic)
# =============================================================================
print('==== CV extragalactic ====')

y_exgal = y[X['f001_hostgal_photoz'] != 0]
target_dict_exgal = {}
target_dict_r_exgal = {}
for i,e in enumerate(y_exgal.sort_values().unique()):
    target_dict_exgal[e] = i
    target_dict_r_exgal[i] = e

y_exgal = y_exgal.replace(target_dict_exgal)
param['num_class'] = i+1


dtrain = lgb.Dataset(X[X['f001_hostgal_photoz'] != 0], y_exgal, #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()

model_all = []
nround_mean = 0
wloss_list = []
for i in range(LOOP):
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         feval=utils.lgb_multi_weighted_logloss_exgal,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    model_all += models
    nround_mean += len(ret['multi_logloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

nround_mean = int((nround_mean/LOOP) * 1.3)

result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
print(result)

imp = ex.getImp(model_all)
imp['split'] /= imp['split'].max()
imp['gain'] /= imp['gain'].max()
imp['total'] = imp['split'] + imp['gain']

imp.sort_values('total', ascending=False, inplace=True)
imp.reset_index(drop=True, inplace=True)


imp.to_csv(f'LOG/imp_{__file__}_exgal.csv', index=False)

png = f'LOG/imp_{__file__}_exgal.png'
utils.savefig_imp(imp, png, x='total', title=f'{__file__}_exgal')
utils.send_line(result, png)


COL_exgal = imp[imp.gain>0].feature.tolist()

# =============================================================================
# model(extragalactic)
# =============================================================================

dtrain = lgb.Dataset(X[X['f001_hostgal_photoz'] != 0], y_exgal, #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()


np.random.seed(SEED)

model_all = []
for i in range(LOOP):
    print('building', i)
    gc.collect()
    param['seed'] = np.random.randint(9999)
    model = lgb.train(param, dtrain, num_boost_round=nround_mean, valid_sets=None, 
                      valid_names=None, fobj=None, feval=None, init_model=None, 
                      feature_name='auto', categorical_feature='auto', 
                      early_stopping_rounds=None, evals_result=None, 
                      verbose_eval=True, learning_rates=None, 
                      keep_training_booster=False, callbacks=None)
    
    model_all.append(model)



model_all_exgal = model_all

del dtrain; gc.collect()

# =============================================================================
# test
# =============================================================================

files_te = sorted(glob('../data/test_f*.pkl'))

X_test = pd.concat([
                pd.read_pickle(f) for f in tqdm(files_te, mininterval=60)
               ], axis=1)

X_test_gal   = X_test[X_test['f001_hostgal_photoz'] == 0][COL_gal]
X_test_exgal = X_test[X_test['f001_hostgal_photoz'] != 0][COL_exgal]

del X_test; gc.collect()


# gal
for i,model in enumerate(tqdm(model_all_gal)):
    y_pred = model.predict(X_test_gal)
    if i==0:
        y_pred_all_gal = y_pred
    else:
        y_pred_all_gal += y_pred
y_pred_all_gal /= len(model_all_gal)
y_pred_all_gal = pd.DataFrame(y_pred_all_gal)
y_pred_all_gal.columns = [f'class_{target_dict_r_gal[x]}' for x in range(len(target_dict_r_gal))]


# exgal
for i,model in enumerate(tqdm(model_all_exgal)):
    y_pred = model.predict(X_test_exgal)
    if i==0:
        y_pred_all_exgal = y_pred
    else:
        y_pred_all_exgal += y_pred
y_pred_all_exgal /= len(model_all_exgal)
y_pred_all_exgal = pd.DataFrame(y_pred_all_exgal)
y_pred_all_exgal.columns = [f'class_{target_dict_r_exgal[x]}' for x in range(len(target_dict_r_exgal))]


sub = pd.concat([y_pred_all_gal, y_pred_all_exgal], ignore_index=True).fillna(0)



# Compute preds_99 as the proba of class not being any of the others
# preds_99 = 0.1 gives 1.769
preds_99 = np.ones(sub.shape[0])
for i in range(sub.shape[1]):
    preds_99 *= (1 - sub.iloc[:, i])
sub['class_99'] = preds_99


oid = pd.concat([pd.read_pickle('../data/oid_gal.pkl'), 
                 pd.read_pickle('../data/oid_exgal.pkl')], 
            ignore_index=True)

sub['object_id'] = oid['object_id'].values

sub.to_csv(SUBMIT_FILE_PATH, index=False, compression='gzip')

sub.iloc[:, 1:].hist(bins=30, figsize=(16, 12))

png = f'LOG/sub_{__file__}.png'
utils.savefig_sub(sub, png)
utils.send_line('DONE!', png)

# =============================================================================
# submission
# =============================================================================
if EXE_SUBMIT:
    print('submit')
    utils.submit(SUBMIT_FILE_PATH, COMMENT)





#==============================================================================
utils.end(__file__)
utils.stop_instance()

