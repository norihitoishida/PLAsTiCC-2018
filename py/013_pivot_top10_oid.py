#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  9 00:55:05 2018

@author: Kazuki

highest flux top10 date diff

keys: object_id


"""

import numpy as np
import pandas as pd
import os
from glob import glob
from scipy.stats import kurtosis
from multiprocessing import cpu_count, Pool

import sys
argvs = sys.argv

from itertools import combinations
import utils

PREF = 'f013'


os.system(f'rm ../data/t*_{PREF}*')
os.system(f'rm ../feature/t*_{PREF}*')

def quantile(n):
    def quantile_(x):
        return np.percentile(x, n)
    quantile_.__name__ = 'q%s' % n
    return quantile_

def kurt(x):
    return kurtosis(x)

stats = ['min', 'max', 'mean', 'median', 'std','skew',
         kurt, quantile(10), quantile(25), quantile(75), quantile(90)]

num_aggregations = {
    'flux':        stats,
    'flux_norm1':  stats,
    'flux_norm2':  stats,
    'flux_norm3':  stats,
    'flux_err':    stats,
    'detected':    stats,
    'flux_ratio_sq': stats,
    'flux_by_flux_ratio_sq': stats,
    'lumi': stats,
    
    'date_diff':   stats,
    }

def aggregate(df, output_path, drop_oid=True):
    """
    df = pd.read_pickle('../data/train_log.pkl').head(999)
    """
    
    df.sort_values(['object_id', 'flux'], ascending=[True, False], inplace=True)
    
    df1 = df.groupby('object_id').head(10).sort_values(['object_id', 'mjd'])
    df1['date_diff'] = df1.groupby('object_id').date.diff()
    
    pt = pd.pivot_table(df1, index=['object_id'],
                        aggfunc=num_aggregations)
    
    pt.columns = pd.Index([f'{e[0]}_{e[1]}' for e in pt.columns.tolist()])
    
    # std / mean
    col_std = [c for c in pt.columns if c.endswith('_std')]
    for c in col_std:
        pt[f'{c}-d-mean'] = pt[c]/pt[c.replace('_std', '_mean')]
    
    # max / min, max - min
    col_max = [c for c in pt.columns if c.endswith('_max')]
    for c in col_max:
        pt[f'{c}-d-min'] = pt[c]/pt[c.replace('_max', '_min')]
        pt[f'{c}-m-min'] = pt[c]-pt[c.replace('_max', '_min')]
    
    # q75 - q25, q90 - q10
    col = [c for c in pt.columns if c.endswith('_q75')]
    for c in col:
        x = c.replace('_q75', '')
        pt[f'{x}_q75-m-q25'] = pt[c] - pt[c.replace('_q75', '_q25')]
        pt[f'{x}_q90-m-q10'] = pt[c.replace('_q75', '_q90')] - pt[c.replace('_q75', '_q10')]
    
    
#    if usecols is not None:
#        col = [c for c in pt.columns if c not in usecols]
#        pt.drop(col, axis=1, inplace=True)
    
    if drop_oid:
        pt.reset_index(drop=True, inplace=True)
    else:
        pt.reset_index(inplace=True)
    pt.add_prefix(PREF+'_').to_pickle(output_path)
    
    return

def multi(args):
    input_path, output_path = args
    aggregate(pd.read_pickle(input_path), output_path, drop_oid=False)
    return

# =============================================================================
# main
# =============================================================================
if __name__ == "__main__":
    utils.start(__file__)
    
    usecols = None
    aggregate(pd.read_pickle('../data/train_log.pkl'), f'../data/train_{PREF}.pkl')
    
    if utils.GENERATE_AUG:
        os.system(f'rm ../data/tmp_{PREF}*')
        argss = []
        for i,file in enumerate(utils.AUG_LOGS):
            argss.append([file, f'../data/tmp_{PREF}{i}.pkl'])
        pool = Pool( cpu_count() )
        pool.map(multi, argss)
        pool.close()
        df = pd.concat([pd.read_pickle(f) for f in glob(f'../data/tmp_{PREF}*')], 
                        ignore_index=True)
        df.sort_values(f'{PREF}_object_id', inplace=True)
        df.reset_index(drop=True, inplace=True)
        del df[f'{PREF}_object_id']
        utils.to_pkl_gzip(df, f'../data/train_aug_{PREF}.pkl')
        os.system(f'rm ../data/tmp_{PREF}*')
    
    # test
    if utils.GENERATE_TEST:
        imp = pd.read_csv(utils.IMP_FILE).head(utils.GENERATE_FEATURE_SIZE)
        usecols = imp[imp.feature.str.startswith(f'{PREF}')][imp.gain>0].feature.tolist()
#        usecols = [c.replace(f'{PREF}_', '') for c in usecols]
#        usecols += ['object_id']
        
        os.system(f'rm ../data/tmp_{PREF}*')
        argss = []
        for i,file in enumerate(utils.TEST_LOGS):
            argss.append([file, f'../data/tmp_{PREF}{i}.pkl'])
        pool = Pool( cpu_count() )
        pool.map(multi, argss)
        pool.close()
        df = pd.concat([pd.read_pickle(f) for f in glob(f'../data/tmp_{PREF}*')], 
                        ignore_index=True)
        df.sort_values(f'{PREF}_object_id', inplace=True)
        df.reset_index(drop=True, inplace=True)
        del df[f'{PREF}_object_id']
        utils.to_pkl_gzip(df, f'../data/test_{PREF}.pkl')
        utils.save_test_features(df[usecols])
        os.system(f'rm ../data/tmp_{PREF}*')
    
    utils.end(__file__)
