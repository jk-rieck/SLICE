#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 11:40:47 2022

@author: Amelie
"""
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import calendar
from netCDF4 import Dataset
from functions import ncdump
from cdo import Cdo
cdo = Cdo()
cdo = Cdo(tempdir='/Volumes/SeagateUSB/McGill/Postdoc/slice/prog/temp_files/') #python

#%%

def ensemble_avg(var_in):
    var_out = np.zeros((12,var_in.shape[1],var_in.shape[2]))*np.nan
    for imonth in range(12):
        var_out[imonth,:,:] = np.nanmean(var_in[imonth:240:12,:,:],axis=0)

    return var_out


def ensemble_clim_monthly(feature,month,year_start=1981,year_end=2010):
    var_out = np.zeros((year_end-year_start+1,12,180,360))*np.nan

    for iyr,year in enumerate(np.arange(year_start,year_end+1)):
        extension = "_{}-{}_allmembers.grib2.nc".format(year, str(month).rjust(2, '0'))
        filename = base + res + feature + extension
        path = r_dir + "{}-{}/".format(year, str(month).rjust(2, '0'))
        ncid = Dataset(path+filename,'r')
        ndump = ncdump(ncid, verb=False)
        v = ndump[2][-1]
        var = np.squeeze(ncid[v][:])

        var_ensm = ensemble_avg(var)
        var_out[iyr,:,:,:] = var_ensm

    return np.squeeze(np.nanmean(var_out,axis=0)), np.squeeze(np.nanstd(var_out,axis=0))


#%%

feature_list = ['WTMP_SFC_0',
                'PRATE_SFC_0',
                'TMP_TGL_2m',
                #'TMP_ISBL_0850',
                'PRMSL_MSL_0',
                #'HGT_ISBL_0500',
                #'UGRD_ISBL_0200',
                #'UGRD_ISBL_0850',
                #'VGRD_ISBL_0200',
                #'VGRD_ISBL_0850',
                #'WSPGRD_ISBL_0850',
                ]

base = "cansips_hindcast_raw_"
res = "latlon1.0x1.0_"
r_dir = '/Volumes/SeagateUSB/McGill/Postdoc/slice/data/raw/CanSIPS/hindcast/raw/'
p_dir = '/Volumes/SeagateUSB/McGill/Postdoc/slice/data/processed/CanSIPS/hindcast/'

ys = 1981
ye = 2010

years_cansips = np.arange(1980,2021)
years = np.arange(1979,2022)

cansips_ensm = np.zeros( ( len(feature_list), len(years), 4, 4, 180, 360 )  )*np.nan
cansips_clim = np.zeros( ( len(feature_list), len(years), 4, 4, 180, 360 )  )*np.nan
cansips_clim_std = np.zeros( ( len(feature_list), len(years), 4, 4, 180, 360 )  )*np.nan
cansips_anom = np.zeros( ( len(feature_list), len(years), 4, 4, 180, 360 )  )*np.nan


for f,feature in enumerate(feature_list):
    for imonth,month in enumerate(np.arange(9,13)):

        # Get the ensemble mean seasonal forecasts for each year and each season:
        for iyr,year in enumerate(years):
            if year in years_cansips:
                extension = "_{}-{}_allmembers.grib2.nc".format(year, str(month).rjust(2, '0'))
                filename = base + res + feature + extension
                path = r_dir + "{}-{}/".format(year, str(month).rjust(2, '0'))
                ncid = Dataset(path+filename,'r')
                ndump = ncdump(ncid, verb=False)
                v = ndump[2][-1]
                var = np.squeeze(ncid[v][:])

                # Get the ensemble mean forecast for each forecast month:
                var_ensm = ensemble_avg(var)

                # Then reorganize to have the ensemble mean seasonal forecast
                # for each season (SON, OND, NDJ, DJF):
                for iseason in range(4-imonth):
                    ind = iseason + imonth # cansips_ensm[f, iyr, imonth, ind, :, :]

                    imonth1 = iseason
                    imonth2 = imonth1 +1
                    imonth3 = imonth1 +2
                    print(feature,year,imonth,iseason)

                    var_season = np.nanmean(var_ensm[imonth1:imonth3+1,:,:],axis=0)
                    cansips_ensm[f, iyr, imonth, ind, :, :] = var_season


        # Compute climatology of seasonal forecasts for each season,
        # then remove from mean seasonal forecasts to get anomaly:
        iyr_s = np.where(years == ys)[0][0]
        iyr_e = np.where(years == ye)[0][0] + 1

        clim = np.nanmean(cansips_ensm[f, iyr_s:iyr_e, imonth, :, :, :],axis=0)
        clim_std = np.nanstd(cansips_ensm[f, iyr_s:iyr_e, imonth, :, :, :],axis=0)

        for iyr,year in enumerate(years):
            var_ensm_clim = clim
            var_ensm_clim_std = clim_std
            var_anomaly = cansips_ensm[f, iyr, imonth, :, :, :]-clim

            cansips_clim[f,iyr,imonth,:,:,:] = var_ensm_clim
            cansips_clim_std[f,iyr,imonth,:,:,:] = var_ensm_clim_std
            cansips_anom[f,iyr,imonth,:,:,:] = var_anomaly



np.savez(p_dir+base+res+'ensemble_vars_sep_dec_fseasonal',
          ensm = cansips_ensm,
          clim = cansips_clim,
          clim_std = cansips_clim_std,
          anomaly = cansips_anom,
          feature_list = feature_list,
          years = years,
          clim_start_yr = ys,
          clim_end_yr = ye,
          lat = ncid['lat'][:],
          lon = ncid['lon'][:])






#%%
# region = 'YUL'
# if region == 'D':
#     # REGION D: ERA5
#     # rlon1, rlat1 = -77.25, 43.25
#     # rlon2, rlat2 = -73.25, 46.00
#     rlon1, rlat1 = 360-77.5, 43.5
#     rlon2, rlat2 = 360-73.5, 46.5
# if region == 'YUL':
#     rlon1, rlat1 = 360-74.5, 45.5
#     rlon2, rlat2 = 360-73.5, 45.5
# if region == 'all':
#     rlon1, rlat1 = 0.5, -89.5
#     rlon2, rlat2 = 359.5,  89.5

# lat = ncid['lat'][:]
# lon = ncid['lon'][:]
# ilat1 = np.where(lat == rlat1)[0][0]
# ilat2 = np.where(lat == rlat2)[0][0]+1
# ilon1 = np.where(lon == rlon1)[0][0]
# ilon2 = np.where(lon== rlon2)[0][0]+1

# var_select = var[:,ilat1:ilat2,ilon1:ilon2]
# var_anomaly_select = var_anomaly[:,ilat1:ilat2,ilon1:ilon2]


# plt.figure()
# plt.imshow(var_anomaly_select[0,:,:],vmin=-1,vmax=1)
# plt.colorbar()

# tmp = np.nanmean(ensm_mean_anom[0,:,:,:,ilat1:ilat2,:],axis=3)
# # tmp = np.nanmean(cansips_anom[0,:,:,:,ilat1:ilat2,:],axis=3)
# var_sel = np.nanmean(tmp[:,:,:,ilon1:ilon2],axis=3)

# plt.figure()
# plt.plot(years,var_sel[:,0,3],'-o')
# plt.plot(years,var_sel[:,0,2],'-o')
# plt.plot(years,var_sel[:,0,1],'-o')
# plt.plot(years,var_sel[:,0,0],'-o')

# plt.figure()
# plt.plot(years,var_sel[:,1,2],'-o')
# plt.plot(years,var_sel[:,1,1],'-o')
# plt.plot(years,var_sel[:,1,0],'-o')

# plt.figure()
# plt.plot(years,var_sel[:,2,1],'-o')
# plt.plot(years,var_sel[:,2,0],'-o')

# plt.figure()
# plt.plot(years,var_sel[:,3,0],'-o')


#%%
import cartopy.crs as ccrs

def plot_contours_cartopy(var,
                          gridlats,
                          gridlons,
                          proj=ccrs.PlateCarree(),
                          vmin = -30,
                          vmax = 30,
                          colormap ='BrBG'):

    plt.figure(figsize=(6,2.5))
    ax = plt.axes(projection = proj)
    ax.coastlines()
    plt.contourf(gridlons,gridlats, var,levels=np.arange(vmin,vmax+1,2),cmap=plt.get_cmap(colormap),transform=proj)
    plt.colorbar()

    # Add contour:
    line_c = ax.contour(gridlons, gridlats, var, levels=np.arange(vmin,vmax+1,2),
                        colors='black',linestyles='dotted',
                        transform=proj)
    plt.setp(line_c.collections, visible=True)

def plot_pcolormesh_cartopy(var,gridlats,gridlons,proj=ccrs.PlateCarree()):
    plt.figure()
    ax = plt.axes(projection = proj)
    plt.pcolormesh(gridlons, gridlats, var)
    ax.coastlines()
    plt.show()



lat = ncid['lat'][:]
lon = ncid['lon'][:]
JFM = np.nanmean(var_ensm_clim[0:3,:,:],axis=0)
JFM = JFM -273.15
plot_contours_cartopy(JFM,lat,lon,vmin = -38,vmax = 8,colormap ='jet')
plot_pcolormesh_cartopy(JFM,lat,lon,proj=ccrs.PlateCarree())

