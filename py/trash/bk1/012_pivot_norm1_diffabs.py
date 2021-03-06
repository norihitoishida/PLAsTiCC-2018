#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 29 23:19:56 2018

@author: kazuki.onodera

TODO: handle sparce

pt[pt.object_id==52422308]
Out[12]: 
        object_id   date       pb0       pb1       pb2       pb3       pb4       pb5
523301   52422308  59629       NaN       NaN       NaN       NaN -0.159185       NaN
523302   52422308  59631       NaN       NaN       NaN -0.320631       NaN       NaN
523303   52422308  59636       NaN       NaN       NaN       NaN -0.082345       NaN
523304   52422308  59660       NaN       NaN       NaN       NaN       NaN -0.359483
523305   52422308  59661       NaN       NaN       NaN       NaN  0.480643       NaN
523306   52422308  59663       NaN       NaN       NaN       NaN       NaN -0.256829
523307   52422308  59666       NaN       NaN       NaN       NaN       NaN -0.048265
523308   52422308  59670       NaN       NaN       NaN       NaN  0.412207       NaN
523309   52422308  59675       NaN       NaN -0.477834       NaN       NaN       NaN
523310   52422308  59688       NaN       NaN       NaN       NaN  0.408257       NaN
523311   52422308  59690       NaN       NaN       NaN -0.388374       NaN       NaN
523312   52422308  59709       NaN       NaN       NaN  0.507281       NaN       NaN
523313   52422308  59712       NaN       NaN       NaN       NaN       NaN  0.003879

"""

import numpy as np
import pandas as pd
import os, gc
from glob import glob
from multiprocessing import cpu_count, Pool
import utils

PREF = 'f012'

os.system(f'rm ../data/t*_{PREF}*')
os.system(f'rm ../feature/t*_{PREF}*')

def quantile(n):
    def quantile_(x):
        return np.percentile(x, n)
    quantile_.__name__ = 'q%s' % n
    return quantile_

stats = ['min', 'max', 'mean', 'median', 'std', quantile(25), quantile(75)]

num_aggregations = {
    'pb0_diff': stats, 
    'pb1_diff': stats, 
    'pb2_diff': stats, 
    'pb3_diff': stats, 
    'pb4_diff': stats, 
    'pb5_diff': stats, 
    
    'pb0_diff_abs': stats, 
    'pb1_diff_abs': stats, 
    'pb2_diff_abs': stats, 
    'pb3_diff_abs': stats, 
    'pb4_diff_abs': stats, 
    'pb5_diff_abs': stats, 
    }

def aggregate(df, output_path, drop_oid=True):
    
    df['date'] = df.mjd.astype(int)
    df.flux /= df.groupby(['object_id']).flux.transform('max')
    
    pt = pd.pivot_table(df, index=['object_id', 'date'], columns=['passband'], values=['flux'])
    pt.columns = pd.Index([f'pb{e[1]}' for e in pt.columns.tolist()])
    pt.reset_index(inplace=True)
    
    df_diff = pt.diff().add_suffix('_diff')
    df_diff_abs = df_diff.abs().add_suffix('_abs')
    df_diff = pd.concat([df_diff, df_diff_abs], axis=1)
    df_diff.loc[pt['object_id'] != pt['object_id'].shift()] = np.nan
    df_diff.drop('object_id_diff', axis=1, inplace=True)
    df_diff['object_id'] = pt['object_id']
    
    
    del df; gc.collect()
    
    df_agg = df_diff.groupby('object_id').agg(num_aggregations)
    df_agg.columns = pd.Index([e[0] + "_" + e[1] for e in df_agg.columns.tolist()])
    
    # std / mean
    col_std = [c for c in df_agg.columns if c.endswith('_std')]
    for c in col_std:
        df_agg[f'{c}-d-mean'] = df_agg[c]/df_agg[c.replace('_std', '_mean')]
    
    # max / min
    col_max = [c for c in df_agg.columns if c.endswith('_max')]
    for c in col_max:
        df_agg[f'{c}-d-min'] = df_agg[c]/df_agg[c.replace('_max', '_min')]
    
    if drop_oid:
        df_agg.reset_index(drop=True, inplace=True)
    else:
        df_agg.reset_index(inplace=True)
    df_agg.add_prefix(PREF+'_').to_pickle(output_path)
    
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
    
    aggregate(pd.read_pickle('../data/train_log.pkl'), f'../data/train_{PREF}.pkl')
    
    # test
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
    os.system(f'rm ../data/tmp_{PREF}*')
    
    utils.end(__file__)

