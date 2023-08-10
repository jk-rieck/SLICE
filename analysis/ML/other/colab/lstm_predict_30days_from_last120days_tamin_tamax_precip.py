# -*- coding: utf-8 -*-
"""LSTM_predict_30days_from_last120days_Tamin_Tamax_precip.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JFHeAzON_Y4jBo_IFezjbg56aL2HzYr1
"""

import numpy as np
import pandas as pd
import datetime as dt
import tensorflow.keras.backend as K

from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from tensorflow import keras
from tensorflow.keras.utils import plot_model

def regression_metrics(y_true, y_pred, verbose=False):
    """
    This function computes regression metrics, i.e.
     - Mean Absolute Error (MAE)
     - Root Mean Square Error (RMSE)
     - Coefficient of determination (R^2)

    :param y_true: Observed traget
    :param y_pred: Predicted target

    :return: mae, rmse, rsqr:
    """
    import sklearn.metrics as metrics

    explained_variance = metrics.explained_variance_score(y_true, y_pred,multioutput='raw_values')
    mean_absolute_error = metrics.mean_absolute_error(y_true, y_pred,multioutput='raw_values')
    mse = metrics.mean_squared_error(y_true, y_pred,multioutput='raw_values')
    # mean_squared_log_error=metrics.mean_squared_log_error(y_true, y_pred,multioutput='raw_values')
    # median_absolute_error=metrics.median_absolute_error(y_true, y_pred,multioutput='raw_values')
    r2 = metrics.r2_score(y_true, y_pred,multioutput='raw_values')

    if verbose:
        # print('explained_variance: ', round(explained_variance,2))
        print('r2: ', np.round(r2,2))
        print('MAE: ', np.round(mean_absolute_error,2))
        print('RMSE: ', np.round(np.sqrt(mse),2))

    return r2, mean_absolute_error, np.sqrt(mse)

def rolling_climo(Nwindow,ts_in,array_type,time,years,date_ref = dt.date(1900,1,1)):
    import calendar

    ts_daily = np.zeros((Nwindow,366,len(years)))*np.nan

    for it in range(ts_in.shape[0]):

        iw0 = np.max([0,it-int((Nwindow-1)/2)])
        iw1 = it+int((Nwindow-1)/2)+1

        ts_window = ts_in[iw0:iw1]
        date_mid = date_ref+dt.timedelta(days=int(time[it]))
        year_mid = date_mid.year
        month_mid = date_mid.month
        day_mid = date_mid.day

        if len(np.where(years == year_mid)[0]) > 0:
            iyear = np.where(years == year_mid)[0][0]
            doy = (dt.date(year_mid,month_mid,day_mid)-dt.date(year_mid,1,1)).days

            ts_daily[0:len(ts_window),doy,iyear] = ts_window

            if not calendar.isleap(year_mid) and (doy == 364) and (year_mid != years[-1]):
                imid = int((Nwindow-1)/2)
                ts_window_366 = np.zeros((Nwindow))*np.nan
                ts_window_366[imid] = np.array(np.nanmean([ts_in[it],ts_in[np.nanmin([len(ts_in)-1,it+1])]]))
                ts_window_366[0:imid] = ts_in[int(it+1-((Nwindow-1)/2)):it+1]
                ts_window_366[imid+1:Nwindow] = ts_in[it+1:int(it+1+((Nwindow-1)/2))]
                ts_daily[:,365,iyear] = ts_window_366


    # Then, find the climatological mean and std for each window/date
    if array_type == 'year':
        mean_clim = np.zeros((366))*np.nan
        std_clim = np.zeros((366))*np.nan
        mean_clim[:] = np.nanmean(ts_daily,axis=(0,2))
        std_clim[:] = np.nanstd(ts_daily,axis=(0,2))

    if array_type == 'all_time':
        mean_clim = np.zeros(len(time))*np.nan
        std_clim = np.zeros(len(time))*np.nan

        yr_st = (date_ref+dt.timedelta(days=int(time[0]))).year
        yr_end = (date_ref+dt.timedelta(days=int(time[-1]))).year
        all_years = np.arange(yr_st,yr_end+1)
        for iyr,year in enumerate(all_years):
            istart = np.where(time == (dt.date(int(year),1,1)-date_ref).days)[0][0]
            iend = np.where(time == (dt.date(int(year),12,31)-date_ref).days)[0][0]+1
            if not calendar.isleap(year):
                mean_clim[istart:iend] = np.nanmean(ts_daily,axis=(0,2))[:-1]
                std_clim[istart:iend] = np.nanstd(ts_daily,axis=(0,2))[:-1]
            else:
                mean_clim[istart:iend] = np.nanmean(ts_daily,axis=(0,2))
                std_clim[istart:iend] = np.nanstd(ts_daily,axis=(0,2))


    return mean_clim, std_clim, ts_daily

"""# Loading the dataset
The dataset is composed of the following variables:

*   Dates (in days since 1900-01-01)
*   Daily water temperature (in °C - from the Longueuil water filtration plant)
*   ERA5 weather daily variables (*see belo*w)
*   Daily discharge (in m$^3$/s) and level (in m) for the St-Lawrence River (at Lasalle and Pointe-Claire, respectively)
*   Daily level (in m) for the Ottawa River (at Ste-Anne-de-Bellevue)
*   Daily time series of climate indices (*see below*)
*   Daily time series of monthly and seasonal forecasts from CanSIPS (*see below*)

"""

# The dataset has been copied into an Excel spreadsheet for this example
df = pd.read_excel('/Volumes/SeagateUSB/McGill/Postdoc/slice/data/colab/predictor_data_daily_timeseries.xlsx')

# The dates column is not needed
time = df['Days since 1900-01-01'].values
df.drop(columns='Days since 1900-01-01', inplace=True)

# Keep only specific predictors, for 1992-2020.
df = df[['Avg. Twater',
         'Avg. Ta_max',
         'Avg. Ta_min',
         'Tot. precip.']]

yr_start = 1992
yr_end = 2020
date_ref = dt.date(1900,1,1)
it_start = np.where(time == (dt.date(yr_start,1,1)-date_ref).days)[0][0]
it_end = np.where(time == (dt.date(yr_end+1,1,1)-date_ref).days)[0][0]

df = df[df.columns][it_start:it_end]
time = time[it_start:it_end]

# Show the first 5 and last 5 rows of the dataset
df

# There is a missing data in the water temperature time series...
# This gap occurs in winter 2018, so we will fill it with zeros.
df['Avg. Twater'][9886:9946] = 0

# We also cap all negative water temperature to zero degrees.
df['Avg. Twater'][df['Avg. Twater'] < 0] = 0

# Check if there are other nan values.
print(np.sum(np.isnan(df)))

# Create the time vector for plotting purposes:
first_day = (date_ref+dt.timedelta(days=int(time[0]))).toordinal()
last_day = (date_ref+dt.timedelta(days=int(time[-1]))).toordinal()
time_plot = np.arange(first_day, last_day + 1)

# Plot the observed water temperature time series, which will be the target variable
fig, ax = plt.subplots(figsize=[12, 6])

ax.plot(time_plot, df['Avg. Twater'], color='C0', label='T$_w$')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_xlabel('Time')
ax.set_ylabel('Water temperature $[^{\circ}C]$')
ax.legend(loc='best')
ax.grid(True)

plt.show()

"""# Splitting the dataset + Data scaling
The training will be done on the 1992-2010 period, validated on the 2011-2015 period and tested on the 2016-2021 period.

The training dataset will be used to compute the water temprature climatology.

Then, the data will be normalized between 0 and 1 using a MinMaxScaler to help the learning process.
"""

train_yr_start = 1992 # Training dataset: 1992 - 2010
valid_yr_start = 2011 # Validation dataset: 2011 - 2015
test_yr_start = 2016 # Testing dataset: 2016 - 2021

istart_train = np.where(time_plot == dt.date(train_yr_start, 1, 1).toordinal())[0][0]
istart_valid = np.where(time_plot == dt.date(valid_yr_start, 1, 1).toordinal())[0][0]
istart_test = np.where(time_plot == dt.date(test_yr_start, 1, 1).toordinal())[0][0]

# Compute daily rolling Twater climatology using only training values
Tw_clim = df['Avg. Twater']
nw = 1
train_years = np.arange(train_yr_start,valid_yr_start)
Tw_clim_mean, Tw_clim_std, _ = rolling_climo(nw, df['Avg. Twater'],'all_time',time,train_years)

# Add Tw climatology to dataset
# df['Tw clim.'] = Tw_clim_mean

# Split dataset into training, validation, and test sets
df_train = df[istart_train:istart_valid]
df_valid = df[istart_valid:istart_test]
df_test = df[istart_test:]

time_train = time_plot[istart_train:istart_valid]
time_valid = time_plot[istart_valid:istart_test]
time_test = time_plot[istart_test:]

# Nornmalize the data using the training values
train_values = df_train.values
valid_values = df_valid.values
test_values = df_test.values

# Normalize features between 0 and 1
scaler = MinMaxScaler()
train_values_scaled = scaler.fit_transform(train_values)
valid_values_scaled = scaler.transform(valid_values)
test_values_scaled = scaler.transform(test_values)

"""# Preparing the LSTM samples
The LSTM that will be used will be fed the **last 120 days** of water temperature, precipitation, minimum and maximum air temperatures to **predict the next day** of water temperatures.


All series of 120 days of input variables will be extracted using a rolling window of 1-day.
In this example, a very simple loop is used to generate the dataset. While this is sub-optimal, this helps for understanding the whole process.

**This can take a few minutes.**
"""

# Prediction window length, in days
pred_len = 30

# Input window length, in days
input_len = 120

# Extract all training examples

# Initialization of numpy arrays
train_target_series = np.array([])
train_time_series = np.array([])
train_Twater_series = np.array([])
train_Tamax_series = np.array([])
train_Tamin_series = np.array([])
train_precip_series = np.array([])

i = 0
while i < len(train_values_scaled) - (input_len+pred_len-1):
    if i == 0:
        train_target_series = train_values_scaled[i + input_len:i + input_len+ pred_len, 0]
        train_time_series = time_train[i + input_len:i + input_len+ pred_len]
        train_Twater_series = train_values_scaled[i:i + input_len, 0]
        train_Tamax_series  = train_values_scaled[i:i + input_len, 1]
        train_Tamin_series  = train_values_scaled[i:i + input_len, 2]
        train_precip_series = train_values_scaled[i:i + input_len, 3]

    else:
        train_target_series = np.vstack([train_target_series, train_values_scaled[i + input_len:i + input_len+ pred_len, 0]])
        train_time_series = np.vstack([train_time_series, time_train[i + input_len:i + input_len+ pred_len]])
        train_Twater_series = np.vstack([train_Twater_series, train_values_scaled[i:i + input_len, 0]])
        train_Tamax_series  = np.vstack([train_Tamax_series,  train_values_scaled[i:i + input_len, 1]])
        train_Tamin_series  = np.vstack([train_Tamin_series,  train_values_scaled[i:i + input_len, 2]])
        train_precip_series = np.vstack([train_precip_series, train_values_scaled[i:i + input_len, 3]])

    i += 1

# Extract all valid examples

# Initialization of numpy arrays
valid_target_series = np.array([])
valid_time_series = np.array([])
valid_Twater_series = np.array([])
valid_Tamax_series = np.array([])
valid_Tamin_series = np.array([])
valid_precip_series = np.array([])

i = 0
while i < len(valid_values_scaled) - (input_len+pred_len-1):
    if i == 0:
        valid_target_series = valid_values_scaled[i + input_len:i + input_len+ pred_len, 0]
        valid_time_series = time_valid[i + input_len:i + input_len+ pred_len]
        valid_Twater_series = valid_values_scaled[i:i + input_len, 0]
        valid_Tamax_series  = valid_values_scaled[i:i + input_len, 1]
        valid_Tamin_series  = valid_values_scaled[i:i + input_len, 2]
        valid_precip_series = valid_values_scaled[i:i + input_len, 3]

    else:
        valid_target_series = np.vstack([valid_target_series, valid_values_scaled[i + input_len:i + input_len+ pred_len, 0]])
        valid_time_series = np.vstack([valid_time_series, time_valid[i + input_len:i + input_len+ pred_len]])
        valid_Twater_series = np.vstack([valid_Twater_series, valid_values_scaled[i:i + input_len, 0]])
        valid_Tamax_series  = np.vstack([valid_Tamax_series,  valid_values_scaled[i:i + input_len, 1]])
        valid_Tamin_series  = np.vstack([valid_Tamin_series,  valid_values_scaled[i:i + input_len, 2]])
        valid_precip_series = np.vstack([valid_precip_series, valid_values_scaled[i:i + input_len, 3]])

    i += 1

# Extract all test examples

# Initialization of numpy arrays
test_target_series = np.array([])
test_time_series = np.array([])
test_Twater_series = np.array([])
test_Tamax_series = np.array([])
test_Tamin_series = np.array([])
test_precip_series = np.array([])

i = 0
while i < len(test_values_scaled) - (input_len+pred_len-1):
    if i == 0:
        test_target_series = test_values_scaled[i + input_len:i + input_len+ pred_len, 0]
        test_time_series = time_test[i + input_len:i + input_len+ pred_len]
        test_Twater_series = test_values_scaled[i:i + input_len, 0]
        test_Tamax_series  = test_values_scaled[i:i + input_len, 1]
        test_Tamin_series  = test_values_scaled[i:i + input_len, 2]
        test_precip_series = test_values_scaled[i:i + input_len, 3]

    else:
        test_target_series = np.vstack([test_target_series, test_values_scaled[i + input_len:i + input_len+ pred_len, 0]])
        test_time_series = np.vstack([test_time_series, time_test[i + input_len:i + input_len+ pred_len]])
        test_Twater_series = np.vstack([test_Twater_series, test_values_scaled[i:i + input_len, 0]])
        test_Tamax_series  = np.vstack([test_Tamax_series,  test_values_scaled[i:i + input_len, 1]])
        test_Tamin_series  = np.vstack([test_Tamin_series,  test_values_scaled[i:i + input_len, 2]])
        test_precip_series = np.vstack([test_precip_series, test_values_scaled[i:i + input_len, 3]])

    i += 1

"""Now adjust the samples to have LSTM inputs (X) that are three-dimensional, with the following dimensions:

1.   Samples. One sequence is one sample. A batch is comprised of one or more samples, typically a multiplicator of 8 or 16 (e.g. 32, 512, 1024).
2.   Time Steps. One time step is one point of observation in the sample.
3.   Features. One feature is one observation at a time step.
"""

X_train = np.dstack([
        train_Tamax_series,
        train_Tamin_series,
        train_precip_series,
        # train_Twater_series
        ]
)
y_train = train_target_series
time_train = train_time_series

X_valid = np.dstack([
        valid_Tamax_series,
        valid_Tamin_series,
        valid_precip_series,
        # valid_Twater_series
        ]
)
y_valid = valid_target_series
time_valid = valid_time_series


X_test = np.dstack([
        test_Tamax_series,
        test_Tamin_series,
        test_precip_series,
        # test_Twater_series
        ]
)
y_test = test_target_series
time_test = test_time_series

# Remove examples if they contain nan in them

if (np.sum(np.isnan(X_train)) > 0) | (np.sum(np.isnan(y_train)) > 0):
    list_del_train = (list(np.where(np.isnan(X_train))[0])+list(np.where(np.isnan(y_train))[0]))
    X_train = np.delete(X_train,list_del_train,axis=0)
    y_train = np.delete(y_train,list_del_train,axis=0)
    time_train = np.delete(time_train,list_del_train,axis=0)

if (np.sum(np.isnan(X_valid)) > 0) | (np.sum(np.isnan(y_valid)) > 0):
    list_del_valid = (list(np.where(np.isnan(X_valid))[0])+list(np.where(np.isnan(y_valid))[0]))
    X_valid = np.delete(X_valid,list_del_valid,axis=0)
    y_valid = np.delete(y_valid,list_del_valid,axis=0)
    time_valid = np.delete(time_valid,list_del_valid,axis=0)

if (np.sum(np.isnan(X_test)) > 0) | (np.sum(np.isnan(y_test)) > 0):
    list_del_test = (list(np.where(np.isnan(X_test))[0])+list(np.where(np.isnan(y_test))[0]))
    X_test = np.delete(X_test,list_del_test,axis=0)
    y_test = np.delete(y_test,list_del_test,axis=0)
    time_test = np.delete(time_test,list_del_test,axis=0)

"""## Create and train the LSTM model
In this example, a deep recurrent neural network (RNN) is used with two hidden layers. The type of RNN is a LSTM (Long-Short-Term-Memory) which give access to long enough memory for this type of problem.

Some notes on the model used:
*   Two layers of 20 LSTM nodes
*   Two layers of dropout (20%) will be used to make the model more robust by turning on and off 20% of the nodes at every epoch.
*   One dense layer at the end to group all information into the desired output
*   The objective function used is the Mean Squared Error (MSE)
*   The optimization method used is the Adam which works well for training neural networks.
*   A total of 50 epochs is used to train the model with batch size of 32.



"""

# LSTM of two layers of 20 neurons
# A dense layer of 1 neurons is used to forecast the last day
model_LSTM = keras.models.Sequential([
    keras.layers.LSTM(20, return_sequences=True, input_shape=[input_len, X_train.shape[-1]]),
    keras.layers.Dropout(0.2),
    keras.layers.LSTM(20),
    keras.layers.Dropout(0.2),
    keras.layers.Dense(pred_len,activation='softplus')
])

# Compile and train the model using 50 epochs.
#model_LSTM.compile(loss='mse', optimizer=keras.optimizers.Adam(learning_rate=1e-3))
model_LSTM.compile(loss='mse', optimizer=keras.optimizers.SGD(learning_rate=0.01,momentum=0.9))
# model_LSTM.compile(loss='mse', optimizer='Adam')

h = model_LSTM.fit(
    X_train,
    y_train,
    epochs=50,
    batch_size=32,
    validation_data=(X_valid, y_valid),
    verbose=2
    )

# Show the LSTM model structure
plot_model(
    model_LSTM,
    to_file='model_plot.png',
    show_shapes=True,
    show_layer_names=True
    )

# Show the number of weights of the LSTM
model_LSTM.summary()

"""## Results of the model training
Comparing the training and validation results show that after about 5 epochs, the model started to overfit while not securing additional real performance.
"""

# Plot the training and validation loss (MSE)
plt.plot(h.history['loss'], 'o-')
plt.plot(h.history['val_loss'], 'o-')
plt.grid(True)
plt.legend(['Loss', 'Val loss'])
plt.xlabel('Number of epochs')
plt.ylabel('MSE')

"""## Evaluate the model performance
The model performance is evaluated using typical regression metrics (i.e. MAE, RMSE, R$^2$)



"""

# Get predictions for all examples
y_pred_train = model_LSTM.predict(X_train)
y_pred_valid = model_LSTM.predict(X_valid)
y_pred_test = model_LSTM.predict(X_test)

# All data must be retransformed back using the MinMaxScaler
for i in range(pred_len):
  y_pred_train[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_pred_train[:,i],axis=1), X_train[:,0,:]), axis=1))[:,0]
  y_pred_valid[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_pred_valid[:,i],axis=1), X_valid[:,0,:]), axis=1))[:,0]
  y_pred_test[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_pred_test[:,i],axis=1), X_test[:,0,:]), axis=1))[:,0]

  y_train[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_train[:,i],axis=1), X_train[:,0,:]), axis=1))[:,0]
  y_valid[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_valid[:,i],axis=1), X_valid[:,0,:]), axis=1))[:,0]
  y_test[:,i] = scaler.inverse_transform(np.concatenate((np.expand_dims(y_test[:,i],axis=1), X_test[:,0,:]), axis=1))[:,0]

# Get the regression metrics:
rsqr_train, mae_train, rmse_train =  regression_metrics(y_train,y_pred_train)
rsqr_valid, mae_valid, rmse_valid =  regression_metrics(y_valid,y_pred_valid)
rsqr_test, mae_test, rmse_test =  regression_metrics(y_test,y_pred_test)
print('TRAINING ---')
print('Rsqr = '+ str(np.round(rsqr_train, 2)))
print('MAE = '+ str(np.round(mae_train, 2)))
print('RMSE = '+ str(np.round(rmse_train, 2)))
print(' ')
print('VALIDATION ---')
print('Rsqr = '+ str(np.round(rsqr_valid, 2)))
print('MAE = '+ str(np.round(mae_valid, 2)))
print('RMSE = '+ str(np.round(rmse_valid, 2)))
print(' ')
print('TEST ---')
print('Rsqr = '+ str(np.round(rsqr_test, 2)))
print('MAE = '+ str(np.round(mae_test, 2)))
print('RMSE = '+ str(np.round(rmse_test, 2)))

lead = 10

# Plot predictions - TRAINING
fig, ax = plt.subplots(figsize=[12, 6])

nyrs_plot = 2

ax.plot(time_train[0:nyrs_plot*365,lead], y_train[0:nyrs_plot*365,lead], color='C0', label='Observed T$_w$')
ax.plot(time_train[0:nyrs_plot*365,lead], y_pred_train[0:nyrs_plot*365,lead], color='C3', label='Predicted T$_w$')

ax.set_xticks(np.arange(time_train[0:nyrs_plot*365,lead][0], time_train[0:nyrs_plot*365,lead][-1], step=366))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_xlabel('Time')
ax.set_ylabel('Water temperature $[^{\circ}C]$')
# ax.legend(loc='best')
ax.grid(True)
ax.set_title('LSTM model in training.')

plt.show()

# Plot predictions - TESTING
fig, ax = plt.subplots(figsize=[12, 6])

nyrs_plot = 1

ax.plot(time_test[0:nyrs_plot*365,lead], y_test[0:nyrs_plot*365,lead], color='C0', label='Observed T$_w$')
ax.plot(time_test[0:nyrs_plot*365,lead], y_pred_test[0:nyrs_plot*365,lead], color='C2', label='Predicted T$_w$')

ax.set_xticks(np.arange(time_test[0:nyrs_plot*365,lead][0], time_test[0:nyrs_plot*365,lead][-1], step=366))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_xlabel('Time')
ax.set_ylabel('Water temperature $[^{\circ}C]$')
# ax.legend(loc='best')
ax.grid(True)
ax.set_title('LSTM model in testing.')

plt.show()

it = 65
# Plot predictions - TESTING
fig, ax = plt.subplots(figsize=[12, 6])

ax.plot(time_test[it], y_test[it], color='C0', label='Observed T$_w$')
ax.plot(time_test[it], y_pred_test[it], color='C2', label='Predicted T$_w$')

ax.set_xticks(np.arange(time_test[it][0], time_test[it][-1], step=366))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_xlabel('Time')
ax.set_ylabel('Water temperature $[^{\circ}C]$')
ax.legend(loc='best')
ax.grid(True)
ax.set_title('LSTM model in testing. ')

plt.show()

dt.date.fromordinal(int(time_test[it][0]))