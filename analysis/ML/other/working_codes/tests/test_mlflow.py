#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 21 14:38:35 2022

@author: Amelie
"""
import sys
import os
FCT_DIR = os.path.dirname(os.path.abspath('/Volumes/SeagateUSB/McGill/Postdoc/slice/prog/'+'/prog/'))
if not FCT_DIR in sys.path:
    sys.path.append(FCT_DIR)


import numpy as np
import matplotlib.pyplot as plt
import datetime as dt
import pandas as pd

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.init as init
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

import mlflow

from functions import rolling_climo, deseasonalize_ts
from functions_ML import regression_metrics, sliding_window_samples, make_dataset_from_numpy
from functions_ML import torch_train_model, torch_evaluate_model, plot_losses
from functions_ML import plot_series_1step,plot_series

use_gpu = torch.cuda.is_available()
device = torch.device("cuda:0" if use_gpu else "cpu")


#%% MLFLOW TRACKER OPTIONS
mlflow_track = False
mlflow_path = 'file://'+'/Volumes/SeagateUSB/McGill/Postdoc/slice/prog/mlflow/mlruns'
mlflow_expname = 'First test'


#%% OPTIONS
plot = True

add_DOY = True
add_climo = False # NOT YET IMPLEMENTED.

use_softplus = False
normalize_predictors = True
normalize_target = False
# norm_type == 'mean_std'
norm_type = 'min_max'

ynoneg = True
ytransform = 'None'
# ytransform = 'diff'
# ytransform = 'diff2'
# ytransform = 'remove_clim'
# ytransform = 'remove_clim_diff'
# ytransform = 'remove_clim_diff2'

valid_scheme = 'standard'
# valid_scheme = 'rolling'
# valid_scheme = 'LOO'
train_yr_start = 1992 # [1992 - 2007] = 16 years
valid_yr_start = 2008 # [2008 - 2013] = 6 years
test_yr_start = 2014  # [2014 - 2019] = 6 years

input_window = 90
pred_window = 75

include_target_as_pred = True
# vars_out = []
vars_out = ['Twater','Ta_mean']
# vars_out = ['Twater']

# available:  'Twater','Ta_mean', 'Ta_min', 'Ta_max',
#             'SLP','runoff','snowfall','precip','cloud','windspeed',
#             'wind direction', 'FDD', 'TDD', 'SW', 'LH', 'SH',
#             'discharge','level St-L. River','level Ottawa River',
#             'AMO','SOI','NAO','PDO','ONI','AO','PNA','WP','TNH','SCAND','PT','POLEUR','EPNP','EA','Nino',
#             'Monthly forecast PRATE_SFC_0 - Start Sep. 1st','Monthly forecast TMP_TGL_2m - Start Sep. 1st','Monthly forecast PRMSL_MSL_0 - Start Sep. 1st',
#             'Monthly forecast PRATE_SFC_0 - Start Oct. 1st','Monthly forecast TMP_TGL_2m - Start Oct. 1st','Monthly forecast PRMSL_MSL_0 - Start Oct. 1st',
#             'Monthly forecast PRATE_SFC_0 - Start Nov. 1st','Monthly forecast TMP_TGL_2m - Start Nov. 1st','Monthly forecast PRMSL_MSL_0 - Start Nov. 1st',
#             'Monthly forecast PRATE_SFC_0 - Start Dec. 1st','Monthly forecast TMP_TGL_2m - Start Dec. 1st','Monthly forecast PRMSL_MSL_0 - Start Dec. 1st',
#             'Seasonal forecast PRATE_SFC_0 - Start Sep. 1st','Seasonal forecast TMP_TGL_2m - Start Sep. 1st','Seasonal forecast PRMSL_MSL_0 - Start Sep. 1st',
#             'Seasonal forecast PRATE_SFC_0 - Start Oct. 1st','Seasonal forecast TMP_TGL_2m - Start Oct. 1st','Seasonal forecast PRMSL_MSL_0 - Start Oct. 1st',
#             'Seasonal forecast PRATE_SFC_0 - Start Nov. 1st','Seasonal forecast TMP_TGL_2m - Start Nov. 1st','Seasonal forecast PRMSL_MSL_0 - Start Nov. 1st',
#             'Seasonal forecast PRATE_SFC_0 - Start Dec. 1st','Seasonal forecast TMP_TGL_2m - Start Dec. 1st','Seasonal forecast PRMSL_MSL_0 - Start Dec. 1st']

#%%%%%%%%% SETUP MLFLOW EXPERIMENT
if mlflow_track:
    mlflow.set_tracking_uri(mlflow_path)
    exp_id = mlflow.create_experiment(mlflow_expname)

#%%%%%%%%% 1) Load Data
fpath = '/Volumes/SeagateUSB/McGill/Postdoc/slice/data/ML_timeseries/'
fname = 'ML_dataset_with_cansips.npz'

with np.load(fpath+fname, allow_pickle='TRUE') as data:
    ds = data['data']
    # date_ref = data['date_ref']
    date_ref = dt.date(1900,1,1)
    region_ERA5 = data['region_ERA5']
    region_cansips = data['region_cansips']
    loc_Twater = data['Twater_loc_list']
    loc_discharge = data['loc_discharge']
    loc_level = data['loc_level']
    loc_levelO = data['loc_levelO']
    labels = [k.decode('UTF-8') for k in data['labels']]

# Select variables from data set and convert to DataFrame
if len(vars_out) > 0:
    # Initialize output array and list of selected variables
    ds_out = np.zeros((ds.shape[0],len(vars_out)))
    var_list_out = []

    # First column is always time
    time = ds[:,0]

    # Fill other columns with selected variables
    for k in range(len(vars_out)):
        if vars_out[k] == 'AO':
            idx = np.where(np.array(labels) == 'AO')[0][0]
            ds_out[:,k] = np.squeeze(ds[:,idx])
            var_list_out.append(labels[idx])
        else:
            idx = [i for i,v in enumerate(np.array(labels)) if vars_out[k] in v]
            if ('FDD' in vars_out[k])|('TDD' in vars_out[k]):
                ds_out[:,k] = np.squeeze(ds[:,idx[0]])
                ds_out[:,k][np.isnan(ds_out[:,k])] = 0
            else:
                ds_out[:,k] = np.squeeze(ds[:,idx[0]])
            var_list_out.append(labels[idx[0]])
else:
    time = ds[:,0]
    ds_out = ds[:,1:]
    var_list_out = labels[1:]

year_start = np.where(time == (dt.date(1992,1,1)-date_ref).days)[0][0]
year_end = np.where(time == (dt.date(2021,12,31)-date_ref).days)[0][0]+1

df = pd.DataFrame(ds_out[year_start:year_end],columns=var_list_out)
time = time[year_start:year_end]

#%%%%%%%%% OPTION: Put negative Twater values to zero
if ynoneg:
    df['Avg. Twater'][df['Avg. Twater'] < 0] = 0

#%%%%%%%%% OPTION: Apply transformation to y (target)
if ytransform == 'diff':
    yt = df['Avg. Twater'][1:].values-df['Avg. Twater'][0:-1].values
    yt = np.insert(yt, 0, np.nan)
    yt_r = df['Avg. Twater'][0:].values
if ytransform == 'diff2':
    Tdiff = df['Avg. Twater'][1:].values-df['Avg. Twater'][0:-1].values
    Tdiff = np.insert(Tdiff, 0, np.nan)
    yt = Tdiff[1:] - Tdiff[0:-1]
    yt = np.insert(yt, 0, np.nan)
    yt_r = df['Avg. Twater'][0:].values
    yt_rr = Tdiff[0:]
if ytransform == 'remove_clim':
    nw = 31
    years_climo = np.arange(1992,2003)
    df_deseason = deseasonalize_ts(nw,df.values,df.columns,'all_time',time,years_climo)
    df_deseason = pd.DataFrame(df_deseason,columns=df.columns)
    yt = df_deseason['Avg. Twater'].values
if ytransform == 'remove_clim_diff':
    nw = 31
    years_climo = np.arange(1992,2003)
    df_deseason = deseasonalize_ts(nw,df.values,df.columns,'all_time',time,years_climo)
    df_deseason = pd.DataFrame(df_deseason,columns=df.columns)
    Tw_deseason = df_deseason['Avg. Twater'].values
    yt = Tw_deseason[1:]-Tw_deseason[0:-1]
    yt = np.insert(yt, 0, np.nan)
if ytransform == 'remove_clim_diff2':
    nw = 31
    years_climo = np.arange(1992,2003)
    df_deseason = deseasonalize_ts(nw,df.values,df.columns,'all_time',time,years_climo)
    df_deseason = pd.DataFrame(df_deseason,columns=df.columns)
    Tw_deseason = df_deseason['Avg. Twater'].values
    Tw_deseasondiff = Tw_deseason[1:]-Tw_deseason[0:-1]
    Tw_deseasondiff = np.insert(Tw_deseasondiff, 0, np.nan)
    yt = Tw_deseasondiff[1:] - Tw_deseasondiff[0:-1]
    yt = np.insert(yt, 0, np.nan)

# Add transformed target to dataset:
if ytransform != 'None':
    target_label = 'ytransform'
    df.insert(0, target_label, yt)

    # Check that distribution is more or less Gaussian:
    if plot:
        fig,ax = plt.subplots()
        ax.hist(yt,bins = np.arange(-3,3,0.2))
else:
    target_label = 'Avg. Twater'

#%%%%%%%%% OPTION: Add DOY feature with a sin+cos
if add_DOY:
    year = 365.2425
    doysin = np.zeros((len(df)))*np.nan
    doycos = np.zeros((len(df)))*np.nan
    for it,t in enumerate(time):
        date = date_ref+dt.timedelta(days=t)
        doy = (dt.date(date.year,date.month,date.day)-dt.date(date.year,1,1)).days +1
        doysin[it] = np.sin(doy * (2*np.pi/year))
        doycos[it] = np.cos(doy * (2*np.pi/year))

    df.insert(1, 'sin(DOY)', doysin)
    df.insert(2, 'cos(DOY)', doycos)

#%%%%%%%%% OPTION: Add Tw climatology as predictor
if add_climo:
    print('Need to implement this!!')

#%%%%%%%%% 2) Split data into training, valid, and test sets

# valid_scheme == 'standard':
it_train_start = np.where(time == (dt.date(train_yr_start,4,1)-date_ref).days)[0][0]
it_train_end = np.where(time == (dt.date(valid_yr_start,3,31)-date_ref).days)[0][0]

it_valid_start = np.where(time == (dt.date(valid_yr_start,4,1)-date_ref).days)[0][0]
it_valid_end = np.where(time == (dt.date(test_yr_start,3,31)-date_ref).days)[0][0]

it_test_start = np.where(time == (dt.date(test_yr_start,4,1)-date_ref).days)[0][0]
it_test_end = np.where(time == (dt.date(2020,3,31)-date_ref).days)[0][0]

df_train = df[it_train_start:it_train_end].copy()
df_valid = df[it_valid_start:it_valid_end].copy()
df_test = df[it_test_start:it_test_end].copy()
time_train = time[it_train_start:it_train_end].copy()
time_valid = time[it_valid_start:it_valid_end].copy()
time_test = time[it_test_start:it_test_end].copy()

# Compute Tw climatology using only the training values:
nw = 1
years = np.arange(train_yr_start,valid_yr_start)
Tw_climatology_mean, Tw_climatology_std, _ = rolling_climo(nw, df['Avg. Twater'],'all_time',time,years)

Tw_climatology_mean_train = Tw_climatology_mean[it_train_start:it_train_end]
Tw_climatology_mean_valid = Tw_climatology_mean[it_valid_start:it_valid_end]
Tw_climatology_mean_test  = Tw_climatology_mean[it_test_start:it_test_end]

if plot:
    fig,ax = plt.subplots()
    ax.hist(df_train[target_label],bins = np.arange(-3,3,0.2),density=True,alpha = 0.3)
    ax.hist(df_valid[target_label],bins = np.arange(-3,3,0.2),density=True,alpha = 0.3)
    ax.hist(df_test[target_label],bins = np.arange(-3,3,0.2),density=True,alpha = 0.3)


#%%%%%%%%% OPTION: Normalize predictors & target
if normalize_predictors:
    train_offset_pred = np.zeros(df_train.shape[1])
    train_range_pred = np.zeros(df_train.shape[1])
    for i in range(df_train.shape[1]):
        if df_train.columns[i] != target_label:
            if norm_type == 'mean_std':
                train_offset_pred[i] = np.nanmean(df_train[df_train.columns[i]])
                train_range_pred[i] = np.nanstd(df_train[df_train.columns[i]])
            if norm_type == 'min_max':
                train_offset_pred[i]= np.nanmin(df_train[df_train.columns[i]])
                train_range_pred[i] = np.nanmax(df_train[df_train.columns[i]])-np.nanmin(df_train[df_train.columns[i]])

            df_train[df_train.columns[i]] = (df_train[df_train.columns[i]] - train_offset_pred[i]) / train_range_pred[i]
            df_valid[df_valid.columns[i]] = (df_valid[df_valid.columns[i]] - train_offset_pred[i]) / train_range_pred[i]
            df_test[df_test.columns[i]]  = (df_test[df_test.columns[i]] - train_offset_pred[i]) / train_range_pred[i]

if normalize_target:
    if norm_type == 'mean_std':
        train_offset_tar = np.nanmean(df_train[target_label])
        train_range_tar = np.nanstd(df_train[target_label])
    if norm_type == 'min_max':
        train_offset_tar = np.nanmin(df_train[target_label])
        train_range_tar = np.nanmax(df_train[target_label])-np.nanmin(df_train[target_label])

    df_train[target_label] = (df_train[target_label] - train_offset_tar) / train_range_tar
    df_valid[target_label] = (df_valid[target_label] - train_offset_tar) / train_range_tar
    df_test[target_label]  = (df_test[target_label] - train_offset_tar) / train_range_tar
else:
    train_offset_tar = np.nanmean(df_train[target_label])
    train_range_tar = np.nanstd(df_train[target_label])




if plot:
    fig,ax = plt.subplots(nrows=df.shape[1],ncols=1)
    for i in range(df.shape[1]):
        ax[i].plot(df.iloc[:,i])
    fig.suptitle('Whole data set')

    fig_train,ax_train = plt.subplots(nrows=df_train.shape[1],ncols=1)
    for i in range(df_train.shape[1]):
        ax_train[i].plot(df_train.iloc[:,i])
    fig_train.suptitle('Training data set')

    fig_valid,ax_valid = plt.subplots(nrows=df_valid.shape[1],ncols=1)
    for i in range(df_valid.shape[1]):
        ax_valid[i].plot(df_valid.iloc[:,i])
    fig_valid.suptitle('Valid data set')

    fig_test,ax_test = plt.subplots(nrows=df_test.shape[1],ncols=1)
    for i in range(df_test.shape[1]):
        ax_test[i].plot(df_test.iloc[:,i])
    fig_test.suptitle('Test data set')

#%%%%%%%%% 3) Create windowed samples & targets and DataLoaders
# Setting the seed to a fixed value to be able to reproduce results
seed = 42
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)

# Windowing infos:
input_width = input_window
label_width = pred_window
shift = pred_window
nslide = 1

# Add climatology to columns for the windowing, but then remove it before passing input to model:
df_train['Tw clim'] = Tw_climatology_mean_train
df_valid['Tw clim'] = Tw_climatology_mean_valid
df_test['Tw clim'] = Tw_climatology_mean_test
label_col = [np.where(df_train.columns == target_label)[0][0]]
input_col = np.where(df_train.columns != target_label)[0].tolist()
if include_target_as_pred:
    input_col.append(label_col[0])
input_col.sort()
clim_col =  np.where(df_train.columns == 'Tw clim')[0][0]

input_train, target_train, time_input_train, time_target_train = sliding_window_samples(df_train.values,time_train,input_width,label_width,shift,nslide,input_col,label_col)
input_valid, target_valid, time_input_valid, time_target_valid = sliding_window_samples(df_valid.values,time_valid,input_width,label_width,shift,nslide,input_col,label_col)
input_test,  target_test,  time_input_test,  time_target_test  = sliding_window_samples(df_test.values ,time_test ,input_width,label_width,shift,nslide,input_col,label_col)

yr_input_train = input_train[:,:,np.where(df_train.columns == 'Avg. Twater')[0][0]].copy()
yr_input_valid = input_valid[:,:,np.where(df_valid.columns == 'Avg. Twater')[0][0]].copy()
yr_input_test = input_test[:,:,np.where(df_test.columns == 'Avg. Twater')[0][0]].copy()

_, clim_target_train, _, t1 = sliding_window_samples(df_train.values,time_train,input_width,label_width,shift,nslide,input_col,[np.where(df_train.columns == 'Tw clim')[0][0]])
_, clim_target_valid, _, t2 = sliding_window_samples(df_valid.values,time_valid,input_width,label_width,shift,nslide,input_col,[np.where(df_train.columns == 'Tw clim')[0][0]])
_, clim_target_test, _,  t3 = sliding_window_samples(df_test.values,time_test,input_width,label_width,shift,nslide,input_col,[np.where(df_train.columns == 'Tw clim')[0][0]])
idel = []
for i in range(len(t1)):
    if t1[i] not in time_target_train:
        idel.append(i)
t1 = np.delete(t1,idel,axis=0)
clim_target_train = np.delete(clim_target_train,idel,axis=0)
idel = []
for i in range(len(t2)):
    if t2[i] not in time_target_valid:
        idel.append(i)
t2 = np.delete(t2,idel,axis=0)
clim_target_valid = np.delete(clim_target_valid,idel,axis=0)
idel = []
for i in range(len(t3)):
    if t3[i] not in time_target_test:
        idel.append(i)
t3 = np.delete(t3,idel,axis=0)
clim_target_test = np.delete(clim_target_test,idel,axis=0)

df_train=df_train.drop('Tw clim',1)
df_valid=df_valid.drop('Tw clim',1)
df_test=df_test.drop('Tw clim',1)
input_train=np.delete(input_train,clim_col,axis=2)
input_valid=np.delete(input_valid,clim_col,axis=2)
input_test=np.delete(input_test,clim_col,axis=2)
input_col = np.array(input_col)
input_col = np.delete(input_col,np.where(input_col == clim_col)[0][0])
predictors = df_train.columns[input_col]

# Data Loader info:
bs = 1
shuffle_train = True
shuffle_valid = False
shuffle_test  = False

train_dl = make_dataset_from_numpy(input_train,target_train,bs,shuffle_train)
valid_dl = make_dataset_from_numpy(input_valid,target_valid,bs,shuffle_valid)
test_dl  = make_dataset_from_numpy(input_test,target_test,bs,shuffle_test)

#%%%%%%%%% 4) Define Models

# DENSE (MLP) MODEL, USING MULTIPLE INPUT STEPS TO PREDICT MULTI-STEP AHEAD
class DenseMulti(nn.Module):
    global normalize_target,norm_type,use_softplus

    def __init__(self, input_size, output_size, nneurons, nlayers):
        super(DenseMulti, self).__init__()

        self.linear_in = nn.Linear(input_size, nneurons)
        self.linear_mid = nn.Linear(nneurons, nneurons)
        self.linear_out = nn.Linear(nneurons, output_size)
        self.flatten = nn.Flatten()
        self.layers = nlayers

        # self.linear_in = nn.Linear(input_size, 100)
        # self.linear_mid1 = nn.Linear(100, 100)
        # self.linear_mid2 = nn.Linear(200, 200)
        # self.linear_mid3 = nn.Linear(100, 40)
        # self.linear_out = nn.Linear(40, output_size)

    def forward(self, x):
        x = self.flatten(x)
        x = F.relu(self.linear_in(x))
        n = 1
        while n < self.layers:
            x = F.relu(self.linear_mid(x))
            n += 1
            if n == self.layers:
                break
        if use_softplus:
            if (normalize_target):
                if (norm_type == 'min_max'):
                    out = F.softplus(self.linear_out(x))
                if (norm_type == 'mean_std'):
                    out = self.linear_out(x)
            else:
                if ytransform == 'None':
                    out = F.softplus(self.linear_out(x))
                else:
                    out = self.linear_out(x)
        else:
            out = self.linear_out(x)
        out = torch.unsqueeze(out, -1) # This works for now because there is only one feature out... but not sure how to deal with multiple features out.
        return out


# LSTM MODEL TO PREDICT MULTI-STEP AHEAD
class LSTMLinear(nn.Module):
    global use_softplus
    def __init__(self, input_dim, output_dim, seqlen_target, hidden_size, n_layers):
        super(LSTMLinear, self).__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_size = hidden_size
        self.num_layers = n_layers

        self.LSTM = nn.LSTM(input_size = self.input_dim,
                            hidden_size = self.hidden_size,
                            num_layers = n_layers,
                            batch_first=True)
        self.fwindow = seqlen_target
        self.fc_1 =  nn.Linear(hidden_size, 128) #fully connected 1
        self.fc = nn.Linear(128, seqlen_target) #fully connected last layer
        self.fc_out = nn.Linear(hidden_size, seqlen_target)
        self.relu = nn.ReLU()

    def forward(self, x):

        # inputs to nn.LSTM(): ( x, (h_0, c_0))
        #---------------------------------------
        # x: inputs - tensor of shape (batch size, sequence length, Hin) when batch_first=True
        # h0: initial hidden_state -  tensor of shape (num_layers,batch size,Hout) containing the initial hidden state for each element in the input sequence.
        # c0: initial cell_state -  tensor of shape (num_layers,batch size,Hcell) containing the initial celln state for each element in the input sequence.
        #   with,
        # N = batch size
        # L = sequence length --> context_window
        # Hin = input_size --> input_dim (or nb. of input features)
        # Hout = hidden_size
        # Hcell = hidden_size


        # outputs of nn.LSTM(): ( output, (h_out, c_out))
        #---------------------------------------
        # output:  tensor of shape (batch size,sequence length, Hcell) containing the output features (h_t) from the last layer of the LSTM, for each t.
        # h_out : tensor of shape (num_layers,batch size,Hcell) containing the final hidden state for each element in the sequence.
        # c_out : tensor of shape (num_layers,batch size,Hcell) containing the final cell state for each element in the sequence.
        #---------------------------------------

        # Initialize hidden state and cell state
        h_0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, dtype=torch.float32)
        c_0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, dtype=torch.float32)

        # # Propagate input through LSTM
        # output, (h_out, c_out) = self.LSTM(x, (h_0, c_0))
        # h_out = h_out.view(-1, self.hidden_size)
        # out = self.relu(h_out)#relu on last hidden state
        # out = self.fc_1(out) #first Dense: hidden state to fully connected layer
        # out = self.relu(out) #relu
        # out = self.fc(out) #Final Output: fully connected layer to output size

        output, (h_out, c_out) = self.LSTM(x, (h_0, c_0))
        out = h_out.view(-1, self.hidden_size)
        out = self.relu(out)#relu on last hidden state
        out = self.fc_out(out) #Final Output: fully connected layer to output size

        if use_softplus:
            # Then apply a soft plus to ensure values > 0 if needed:
            if (normalize_target):
                if (norm_type == 'min_max'):
                    out = F.softplus(out)
            else:
                if ytransform == 'None':
                    out = F.softplus(out)

        out = torch.unsqueeze(out, -1) # Not sure why I need this...???

        return out


#%%%%%%%%% 5) Instantiate Model, Loss, and Optimizer

# Instantiate MLP Model
# nb_neurons = 10
# nb_layers = 3
# model = DenseMulti(input_width*len(input_col),label_width*len(label_col), nb_neurons, nb_layers)
# model.to(device)
# model_name = 'MLP'

# train_losses = []
# valid_losses = []

# optimizer = optim.Adam(model.parameters(),lr=5e-6)
# # optimizer = optim.SGD(model.parameters(),lr=5e-5, momentum=0.8)
# loss_function = nn.MSELoss() # Mean square error


# Instantiate LSTM Model
nb_layers = 1
hidden = 32
model = LSTMLinear(len(input_col),len(label_col), seqlen_target=label_width, hidden_size=hidden, n_layers=nb_layers)
model.to(device)
model_name = 'LSTM'

train_losses = []
valid_losses = []

optimizer = optim.Adam(model.parameters(),lr=1e-5)
# optimizer = optim.SGD(model.parameters(),lr=5e-5, momentum=0.9)
loss_function = nn.MSELoss() # Mean square error


#%%%%%%%%% 6) Train Model
n_epochs = 250
print("Optmization started.")
for epoch in range(1, n_epochs + 1):
    train_loss = torch_train_model(epoch, model, train_dl, optimizer, loss_function, device)
    valid_loss = torch_evaluate_model(model, valid_dl, loss_function, device)

    train_losses.append(train_loss)
    valid_losses.append(valid_loss)

print("\n\n\nOptimization ended.\n")
model.eval()

#%%%%%%%%% 7) Plot training and validation Losses
plot_losses(train_losses,valid_losses)


#%%%%%%%%% 8) Evaluate predictions
predictions_train = []
for it in range(input_train.shape[0]):
    input_pred = np.expand_dims(input_train[it,:,:],0)
    predictions_train.append(model(torch.from_numpy(input_pred).float()).detach().numpy())

predictions_valid = []
for it in range(input_valid.shape[0]):
    input_pred = np.expand_dims(input_valid[it,:,:],0)
    predictions_valid.append(model(torch.from_numpy(input_pred).float()).detach().numpy())

predictions_test = []
for it in range(input_test.shape[0]):
    input_pred = np.expand_dims(input_test[it,:,:],0)
    predictions_test.append(model(torch.from_numpy(input_pred).float()).detach().numpy())


#%%
def evaluate_ML_pred(targets,predictions,yr_input,time_in,Tw_climatology_mean,t_range,t_offset,plot_pred_ts = True):
    global input_width, shift, label_width, nslide, pred_window
    global normalize_target, normalize_predictors, ytransform
    global train_range_pred, train_offset_pred


    MAE=nn.L1Loss()
    MSE=nn.MSELoss()
    if normalize_target:
        targets = (np.squeeze(torch.from_numpy(targets).float())*t_range) + t_offset
        predictions = (np.squeeze(torch.from_numpy(np.array(predictions).astype(float)).float())*t_range) + t_offset
    else:
        targets = (np.squeeze(torch.from_numpy(targets).float()))
        predictions = (np.squeeze(torch.from_numpy(np.array(predictions).astype(float)).float()))


    if ytransform == 'diff':
        if normalize_predictors:
            yr = (np.squeeze(torch.from_numpy(yr_input).float())*train_range_pred[np.where(df_valid.columns == 'Avg. Twater')[0][0]]) + train_offset_pred[np.where(df_valid.columns == 'Avg. Twater')[0][0]]
        else:
            yr = (np.squeeze(torch.from_numpy(yr_input).float()))

        targets_recons = np.zeros(targets.shape)
        predictions_recons = np.zeros(predictions.shape)
        for s in range(targets.shape[0]):
            for it in range(label_width):
                if it == 0:
                    targets_recons[s,it] = yr[s,-1] + targets[s,it]
                    predictions_recons[s,it] = yr[s,-1] + predictions[s,it]
                else:
                    targets_recons[s,it] = targets_recons[s,it-1] + targets[s,it]
                    predictions_recons[s,it] = predictions_recons[s,it-1] + predictions[s,it]

        targets_recons = torch.from_numpy((targets_recons)).float()
        predictions_recons = torch.from_numpy((predictions_recons)).float()

    elif ytransform == 'None':
        targets_recons = targets
        predictions_recons = predictions

    print('MLP MODEL, '+ str(pred_window)+ '-STEP AHEAD -----------')
    print('VALID')
    print(MAE(targets_recons,predictions_recons))
    print(np.sqrt(MSE(targets_recons,predictions_recons)))
    print(np.corrcoef(np.array(targets_recons).ravel(),np.array(predictions_recons).ravel())[0,1])

    # Plot predictions:
    if plot_pred_ts:
        plt.figure()
        # First add climatology
        y_renorm_clim = torch.from_numpy((Tw_climatology_mean[input_width:])).float()
        plot_series_1step(time_in[input_width:],np.array(y_renorm_clim).ravel(),'-',ax_labels=['Time', 'T$_{w}$'],linecolor=plt.get_cmap('tab20')(0))
        # Then add model:
        for s in np.arange(0,targets_recons.shape[0]-(input_width+shift),label_width):
            plot_series(time_in[input_width+(nslide*s):input_width+label_width+(nslide*s)],np.array(targets_recons)[s,:],'-',ax_labels=['Time', 'T$_{w}$'],linecolor='black')
            plot_series(time_in[input_width+(nslide*s):input_width+label_width+(nslide*s)],np.array(predictions_recons)[s,:],'-',ax_labels=['Time', 'T$_{w}$'],linecolor=plt.get_cmap('tab20')(2))
        plt.title('Predictors: T$_{air}$, T$_{water}$, |T$_{water}$-T$_{air}$| (previous ' + '%2i'%input_width + 'days)')


# VALIDATION PREDICTIONS
predictions = predictions_valid.copy()
targets = target_valid.copy()
evaluate_ML_pred(targets,predictions,yr_input_valid,time_valid,Tw_climatology_mean_valid,train_range_tar,train_offset_tar,plot_pred_ts = True)


# TRAINING PREDICTIONS
predictions = predictions_train.copy()
targets = target_train.copy()
evaluate_ML_pred(targets,predictions,yr_input_train,time_train,Tw_climatology_mean_train,train_range_tar,train_offset_tar,plot_pred_ts = True)

