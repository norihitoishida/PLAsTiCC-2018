#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  9 18:41:58 2018

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
#utils.start(__file__)
#==============================================================================

SEED = np.random.randint(9999)
print('SEED:', SEED)

#DROP = ['f001_hostgal_specz', 'f001_distmod', 'f701_hostgal_specz']

DROP = []

NFOLD = 5

LOOP = 1

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

X.drop(DROP, axis=1, inplace=True)

if X.columns.duplicated().sum()>0:
    raise Exception(f'duplicated!: { X.columns[X.columns.duplicated()] }')
print('no dup :) ')
print(f'X.shape {X.shape}')

gc.collect()

#CAT = list( set(X.columns)&set(utils_cat.ALL))
#print(f'CAT: {CAT}')

# =============================================================================
# separate
# =============================================================================

is_gal = pd.read_pickle('../data/tr_is_gal.pkl')

X_gal = X[is_gal]
y_gal = y[is_gal]

X_exgal = X[~is_gal]
y_exgal = y[~is_gal]


def target_replace(y):
    target_dict = {}
    target_dict_r = {}
    for i,e in enumerate(y.sort_values().unique()):
        target_dict[e] = i
        target_dict_r[i] = e
    
    return y.replace(target_dict), target_dict_r


y_gal, di_gal = target_replace(y_gal)
y_exgal, di_exgal = target_replace(y_exgal)


del X, y
gc.collect()

print(f'X_gal.shape: {X_gal.shape}')
print(f'X_exgal.shape: {X_exgal.shape}')

# =============================================================================
# cv(gal)
# =============================================================================
param['num_class'] = 5

dtrain = lgb.Dataset(X_gal, y_gal, #categorical_feature=CAT, 
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
    y_pred = ex.eval_oob(X_gal, y_gal, models, SEED, stratified=True, shuffle=True, 
                         n_class=y_gal.unique().shape[0])
    model_all += models
    nround_mean += len(ret['multi_logloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

nround_mean = int((nround_mean/LOOP) * 1.3)

result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
print(result)

utils.send_line(result)
imp = ex.getImp(model_all)
imp['split'] /= imp['split'].max()
imp['gain'] /= imp['gain'].max()
imp['total'] = imp['split'] + imp['gain']

imp.sort_values('total', ascending=False, inplace=True)
imp.reset_index(drop=True, inplace=True)

print(imp.head(200).feature.map(lambda x: x.split('_')[0]).value_counts())

imp.to_csv(f'LOG/imp_{__file__}_gal.csv', index=False)



# =============================================================================
# estimate feature size(gal)
# =============================================================================
print('estimate feature size')

COL = imp.feature.tolist()
best_score = 9999
best_N = 0

for i in np.arange(50, 400, 50):
    print(f'\n==== feature size: {i} ====')
    
    dtrain = lgb.Dataset(X_gal[COL[:i]], y_gal, #categorical_feature=CAT, 
                         free_raw_data=False)
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         feval=utils.lgb_multi_weighted_logloss_gal,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    
    utils.send_line(f"feature size: {i}    wloss-mean: {ret['wloss-mean'][-1]}")
    score = ret['wloss-mean'][-1]
    utils.send_line(f"feature size: {i}    wloss-mean: {score}")
    
    if score < best_score:
        best_score = score
        best_N = i



# =============================================================================
# best(gal)
# =============================================================================
N = 150
dtrain = lgb.Dataset(X_gal[COL[:N]], y_gal, #categorical_feature=CAT, 
                     free_raw_data=False)
ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                     feval=utils.lgb_multi_weighted_logloss_gal,
                     early_stopping_rounds=100, verbose_eval=50,
                     seed=SEED)

score = ret['wloss-mean'][-1]

y_pred_gal = ex.eval_oob(X_gal[COL[:N]], y_gal, models, SEED, stratified=True, shuffle=True, 
                         n_class=y_gal.unique().shape[0])



# =============================================================================
# cv(exgal)
# =============================================================================
param['num_class'] = 9

dtrain = lgb.Dataset(X_exgal, y_exgal, #categorical_feature=CAT, 
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
    y_pred = ex.eval_oob(X_exgal, y_exgal, models, SEED, stratified=True, shuffle=True, 
                         n_class=y_exgal.unique().shape[0])
    model_all += models
    nround_mean += len(ret['multi_logloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

nround_mean = int((nround_mean/LOOP) * 1.3)

result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
print(result)

utils.send_line(result)
imp = ex.getImp(model_all)
imp['split'] /= imp['split'].max()
imp['gain'] /= imp['gain'].max()
imp['total'] = imp['split'] + imp['gain']

imp.sort_values('total', ascending=False, inplace=True)
imp.reset_index(drop=True, inplace=True)

print(imp.head(200).feature.map(lambda x: x.split('_')[0]).value_counts())

imp.to_csv(f'LOG/imp_{__file__}_exgal.csv', index=False)



# =============================================================================
# estimate feature size(exgal)
# =============================================================================
print('estimate feature size')

COL = imp.feature.tolist()
best_score = 9999
best_N = 0
for i in np.arange(50, 400, 50):
    print(f'\n==== feature size: {i} ====')
    
    dtrain = lgb.Dataset(X_exgal[COL[:i]], y_exgal, #categorical_feature=CAT, 
                         free_raw_data=False)
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         feval=utils.lgb_multi_weighted_logloss_exgal,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    score = ret['wloss-mean'][-1]
    utils.send_line(f"feature size: {i}    wloss-mean: {score}")
    
    if score < best_score:
        best_score = score
        best_N = i


# =============================================================================
# best(exgal)
# =============================================================================
N = 150
dtrain = lgb.Dataset(X_exgal[COL[:N]], y_exgal, #categorical_feature=CAT, 
                     free_raw_data=False)
ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                     feval=utils.lgb_multi_weighted_logloss_exgal,
                     early_stopping_rounds=100, verbose_eval=50,
                     seed=SEED)

score = ret['wloss-mean'][-1]

y_pred_exgal = ex.eval_oob(X_gal[COL[:N]], y_exgal, models, SEED, stratified=True, shuffle=True, 
                           n_class=y_exgal.unique().shape[0])

# =============================================================================
# concat
# =============================================================================

y = pd.concat([y_gal, y_exgal], 
              ignore_index=True)


y_pred_gal = pd.DataFrame(y_pred_gal)
y_pred_gal.columns = [f'class_{di_gal[x]}' for x in range(len(di_gal))]

y_pred_exgal = pd.DataFrame(y_pred_exgal)
y_pred_exgal.columns = [f'class_{di_exgal[x]}' for x in range(len(di_exgal))]

y_pred = pd.concat([y_pred_gal, y_pred_exgal], 
                   ignore_index=True).fillna(0)


loss = utils.multi_weighted_logloss(y, y_pred)



# =============================================================================
# confusion matrix
# =============================================================================
import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt
from tqdm import tqdm
from sklearn.metrics import confusion_matrix
import itertools

unique_y = np.unique(y)
class_map = dict()
for i,val in enumerate(unique_y):
    class_map[val] = i
        
y_map = np.zeros((y.shape[0],))
y_map = np.array([class_map[val] for val in y])

# http://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html
def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)
    
    plt.figure(figsize=(12,12))
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")
    
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    plt.savefig(f'LOG/CM_{__file__}.png')



cnf_matrix = confusion_matrix(y_map, np.argmax(y_pred.values, axis=-1))
np.set_printoptions(precision=2)

class_names = ['class_6',
             'class_15',
             'class_16',
             'class_42',
             'class_52',
             'class_53',
             'class_62',
             'class_64',
             'class_65',
             'class_67',
             'class_88',
             'class_90',
             'class_92',
             'class_95']

foo = plot_confusion_matrix(cnf_matrix, classes=class_names,normalize=True,
                      title='Confusion Matrix')

utils.send_line(f'Confusion Matrix wmlogloss: {loss}', png=f'LOG/CM_{__file__}.png')



#==============================================================================
#utils.end(__file__)
#utils.stop_instance()

