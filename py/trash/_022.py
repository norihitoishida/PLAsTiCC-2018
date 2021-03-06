#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 18 13:38:31 2018

@author: Kazuki
"""


import numpy as np
import pandas as pd
import os
from glob import glob
from scipy.stats import kurtosis
from multiprocessing import cpu_count, Pool
from tsfresh.feature_extraction import extract_features

import sys
argvs = sys.argv

import utils

PREF = 'f022'

if len(argvs)>1:
    is_test = int(argvs[1])
else:
    is_test = 0


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
    'lumi':        stats,
    }

fcp = {'fft_coefficient': [{'coeff': 0, 'attr': 'abs'},
                           {'coeff': 1, 'attr': 'abs'}],
        'kurtosis' : None, 'skewness' : None}

def aggregate(df, output_path, drop_oid=True):
    """
    df = pd.read_pickle('../data/train_log.pkl')
    """
    
    pt = pd.pivot_table(df, index=['object_id'], 
                        aggfunc=num_aggregations)
    
    pt.columns = pd.Index([f'{e[0]}_{e[1]}' for e in pt.columns.tolist()])
    
    # std / mean
    col_std = [c for c in pt.columns if c.endswith('_std')]
    for c in col_std:
        pt[f'{c}-d-mean'] = pt[c]/pt[c.replace('_std', '_mean')]
    
    # max / min, max - min, (max - min)/mean
    col_max = [c for c in pt.columns if c.endswith('_max')]
    for c in col_max:
        pt[f'{c}-d-min'] = pt[c]/pt[c.replace('_max', '_min')]
        pt[f'{c}-m-min'] = pt[c]-pt[c.replace('_max', '_min')]
        try:
            pt[f'{c}-m-min-d-mean'] = pt[f'{c}-m-min']/pt[c.replace('_max', '_mean')]
        except:
            pass
    
    # q75 - q25, q90 - q10
    col = [c for c in pt.columns if c.endswith('_q75')]
    for c in col:
        x = c.replace('_q75', '')
        pt[f'{x}_q75-m-q25'] = pt[c] - pt[c.replace('_q75', '_q25')]
        pt[f'{x}_q90-m-q10'] = pt[c.replace('_q75', '_q90')] - pt[c.replace('_q75', '_q10')]
    
    
    
    
    
    if usecols is None:
        n_jobs = cpu_count()
    else:
        n_jobs = 0
    ts1 = extract_features(df, column_id='object_id', column_sort='mjd', 
                                 column_kind='passband', column_value = 'flux', 
                                 default_fc_parameters = fcp, n_jobs=n_jobs).add_prefix('a_')
    ts1.index.name = 'object_id'
    
#    ts2 = extract_features(df, column_id='object_id', column_sort='mjd', 
#                                 column_kind='passband', column_value = 'flux_norm1', 
#                                 default_fc_parameters = fcp, n_jobs=n_jobs).add_prefix('b_')
#    ts2.index.name = 'object_id'
#    
#    ts3 = extract_features(df, column_id='object_id', column_sort='mjd', 
#                                 column_kind='passband', column_value = 'flux_ratio_sq', 
#                                 default_fc_parameters = fcp, n_jobs=n_jobs).add_prefix('c_')
#    ts3.index.name = 'object_id'
#    
#    ts4 = extract_features(df, column_id='object_id', column_sort='mjd', 
#                                 column_kind='passband', column_value = 'flux_by_flux_ratio_sq', 
#                                 default_fc_parameters = fcp, n_jobs=n_jobs).add_prefix('d_')
#    ts4.index.name = 'object_id'
    
    pt = pd.concat([pt, ts1, 
#                    ts2, ts3, ts4
                    ], axis=1)
    
    if usecols is not None:
        col = [c for c in pt.columns if c not in usecols]
        pt.drop(col, axis=1, inplace=True)
    
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
    df = pd.read_pickle('../data/train_log.pkl')
    tr = utils.load_train()
    df = pd.merge(df, tr[['object_id', 'distmod']], on='object_id', how='left')
    df['lumi'] = df['flux'] * 4 * np.pi * 10 ** ((df['distmod']+5)/2.5)
    aggregate(df, f'../data/train_{PREF}.pkl')
    
    # test
    if is_test:
        imp = pd.read_csv(utils.IMP_FILE).head(utils.GENERATE_FEATURE_SIZE)
        usecols = imp[imp.feature.str.startswith(f'{PREF}')][imp.gain>0].feature.tolist()
        usecols = [c.replace(f'{PREF}_', '') for c in usecols]
        usecols += ['object_id']
        
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
        df.to_pickle(f'../data/test_{PREF}.pkl')
        utils.save_test_features(df)
        os.system(f'rm ../data/tmp_{PREF}*')
    
    utils.end(__file__)


