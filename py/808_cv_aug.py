#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct 14 20:22:37 2018

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
print('SEED:', SEED)

DROP = ['f001_hostgal_specz', 'f001_distmod',]# 'f701_hostgal_specz'] # 

#DROP = []

NFOLD = 5

LOOP = 1

param = {
         'objective': 'multiclass',
         'num_class': 14,
         'metric': 'multi_logloss',
         
#         'learning_rate': 0.01,
         'max_depth': 3,
#         'num_leaves': 63,
         'max_bin': 255,
         
         'min_child_weight': 10,
         'min_data_in_leaf': 50,
         'reg_lambda': 0.5,  # L2 regularization term on weights.
         'reg_alpha': 0.5,  # L1 regularization term on weights.
         
         'colsample_bytree': 0.5,
         'subsample': 0.7,
#         'nthread': 32,
         'nthread': cpu_count(),
         'bagging_freq': 1,
         'verbose':-1,
         }

# =============================================================================
# load
# =============================================================================

files_tr = sorted(glob('../data/train_f*.pkl'))
[print(i,f) for i,f in enumerate(files_tr)]

X = pd.concat([
                pd.read_pickle(f) for f in tqdm(files_tr, mininterval=60)
               ], axis=1)
y = utils.load_target().target

X.drop(DROP, axis=1, inplace=True)

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
# cv1
# =============================================================================
param['learning_rate'] = 0.1
dtrain = lgb.Dataset(X, y, #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()

model_all = []
nround_mean = 0
wloss_list = []
for i in range(LOOP):
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         feval=utils_metric.lgb_multi_weighted_logloss,
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
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

print(imp.head(100).feature.map(lambda x: x.split('_')[0]).value_counts())

#imp.to_csv(f'LOG/imp_{__file__}.csv', index=False)

"""

__file__ = '808_cv.py'
imp = pd.read_csv(f'LOG/imp_{__file__}-1.csv')

"""


COL = imp.feature.tolist()[:3000]

# =============================================================================
# load aug
# =============================================================================

files_tr = sorted(glob('../data/train_aug_f*.pkl*'))
[print(i,f) for i,f in enumerate(files_tr)]

def read(f, col):
    df = pd.read_pickle(f)
    col = list(set(col) & set(df.columns))
    return df[col]


X_aug = pd.concat([
                read(f, COL) for f in tqdm(files_tr, mininterval=60)
               ], axis=1)
y_aug = pd.read_pickle('../data/target_aug.pkl').target


target_dict = {}
target_dict_r = {}
for i,e in enumerate(y_aug.sort_values().unique()):
    target_dict[e] = i
    target_dict_r[i] = e

y_aug = y_aug.replace(target_dict)

if X_aug.columns.duplicated().sum()>0:
    raise Exception(f'duplicated!: { X_aug.columns[X_aug.columns.duplicated()] }')
print('no dup :) ')
print(f'X_aug.shape {X_aug.shape}')


X = pd.concat([X, X_aug], ignore_index=True, join='inner')
y = pd.concat([y, y_aug], ignore_index=True)

del X_aug, y_aug
gc.collect()


from sklearn.model_selection import GroupKFold


tr_oid = pd.read_pickle('../data/train.pkl').object_id
aug_oid = pd.read_pickle('../data/train_aug.pkl').object_id_bk

group = tr_oid.append(aug_oid) % NFOLD

group_kfold = GroupKFold(n_splits=NFOLD)


gc.collect()






# =============================================================================
# cv2
# =============================================================================

param['learning_rate'] = 0.5
dtrain = lgb.Dataset(X, y, #categorical_feature=CAT, 
                     free_raw_data=False)
gc.collect()

model_all = []
nround_mean = 0
wloss_list = []
for i in range(1):
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         fobj=utils_metric.wloss_objective, 
                         feval=utils_metric.wloss_metric,
                         folds=group_kfold.split(X, y, group),
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    model_all += models
    nround_mean += len(ret['multi_logloss-mean'])
    wloss_list.append( ret['wloss-mean'][-1] )

#nround_mean = int((nround_mean/LOOP) * 1.3)

result = f"CV wloss: {np.mean(wloss_list)} + {np.std(wloss_list)}"
print(result)

utils.send_line(result)
imp = ex.getImp(model_all)
imp['split'] /= imp['split'].max()
imp['gain'] /= imp['gain'].max()
imp['total'] = imp['split'] + imp['gain']

imp.sort_values('total', ascending=False, inplace=True)
imp.reset_index(drop=True, inplace=True)

print(imp.head(100).feature.map(lambda x: x.split('_')[0]).value_counts())

imp.to_csv(f'LOG/imp_{__file__}-2.csv', index=False)



# =============================================================================
# estimate feature size
# =============================================================================
print('estimate feature size')
param['learning_rate'] = 0.5

COL = imp.feature.tolist()
best_score = 9999
best_N = 0

for i in np.arange(100, 500, 50):
    print(f'\n==== feature size: {i} ====')
    
    dtrain = lgb.Dataset(X[COL[:i]], y, #categorical_feature=CAT, 
                         free_raw_data=False)
    gc.collect()
    param['seed'] = np.random.randint(9999)
    ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                         fobj=utils_metric.wloss_objective, 
                         feval=utils_metric.wloss_metric,
                         folds=group_kfold.split(X, y, group),
                         early_stopping_rounds=100, verbose_eval=50,
                         seed=SEED)
    
    score = ret['wloss-mean'][-1]
    utils.send_line(f"feature size: {i}    wloss-mean: {score}")
    
    if score < best_score:
        best_score = score
        best_N = i

print('best_N', best_N)

# =============================================================================
# best
# =============================================================================
N = best_N
dtrain = lgb.Dataset(X[COL[:N]], y, #categorical_feature=CAT, 
                     free_raw_data=False)
ret, models = lgb.cv(param, dtrain, 99999, nfold=NFOLD, 
                     fobj=utils_metric.wloss_objective, 
                     feval=utils_metric.wloss_metric,
                     early_stopping_rounds=100, verbose_eval=50,
                     seed=SEED)

score = ret['wloss-mean'][-1]

y_pred = ex.eval_oob(X[COL[:N]], y, models, SEED, stratified=True, shuffle=True, 
                     n_class=y.unique().shape[0])

tmp = y_pred.copy()

y_pred = pd.DataFrame(utils_metric.softmax(y_pred.astype(float).values))


y_true = pd.get_dummies(y)


y_true.to_pickle('../data/y_true.pkl')
y_pred.to_pickle('../data/y_pred.pkl')


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



cnf_matrix = confusion_matrix(y_map, np.argmax(y_pred.astype(float).values, axis=-1))
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

foo = plot_confusion_matrix(cnf_matrix, classes=class_names,
                            normalize=True,
                            title='Confusion Matrix')

utils.send_line(f'Confusion Matrix wmlogloss: {score}', png=f'LOG/CM_{__file__}.png')



#==============================================================================
#utils.end(__file__)
#utils.stop_instance()


