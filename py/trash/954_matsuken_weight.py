#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 12 01:31:10 2018

@author: Kazuki
"""

import numpy as np
import pandas as pd
import os
import utils
utils.start(__file__)
#==============================================================================

SUBMIT_FILE_PATH = '../output/0890+w.csv.gz'

COMMENT = '''weight = np.array([0.93518041791149, 1.0371997389092826, 0.7276439651240076, 
                   0.6327491122383724, 1.1299087345271177, 1.5915423992967905, 
                   0.7171293513633095, 1.4088185214955187, 0.5753104825120527, 
                   1.0969786180736176, 0.8075063922456374, 0.5918521326189743, 
                   1.1820632733042782, 0.9285728506117077, 1])'''

sub = pd.read_csv('../FROM_MYTEAM/v103_068__v103_062_specz_avg.csv.gz')

weight = np.array([0.93518041791149, 1.0371997389092826, 0.7276439651240076, 
                   0.6327491122383724, 1.1299087345271177, 1.5915423992967905, 
                   0.7171293513633095, 1.4088185214955187, 0.5753104825120527, 
                   1.0969786180736176, 0.8075063922456374, 0.5918521326189743, 
                   1.1820632733042782, 0.9285728506117077, 1])

val = sub.iloc[:, 1:].values
val = np.clip(a=val, a_min=0, a_max=1)
if weight is not None:
    val *= weight
val /= val.sum(1)[:,None]
sub.iloc[:, 1:] = val

sub.to_csv(SUBMIT_FILE_PATH, index=False, compression='gzip')

utils.submit(SUBMIT_FILE_PATH, COMMENT)

#==============================================================================
utils.end(__file__)
utils.stop_instance()


