import xarray as xr
import numpy as np
import matplotlib.pyplot as plt


file = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/vent_arpege_anaMAN.20090121-26.ATL.grb"

A = xr.load_dataset(file, engine='cfgrib')

LON, LAT = np.meshgrid(A.longitude.data, A.latitude.data)

for t in range(25):
    for s in range(2):
        plt.figure()
        D = np.sqrt(A.isel(time=t, step=s).u10**2 + A.isel(time=t, step=s).v10**2)
        scb = plt.pcolor(LON.T, LAT.T, D, cmap='jet', vmin=0, vmax=30)
        plt.quiver(LON.T[::2], 
                   LAT.T[::2], 
                   A.isel(time=t, step=s).u10.data[::2],
                   A.isel(time=t, step=s).v10.data[::2])
        plt.colorbar(scb)
        plt.show()
        
for t in range(25):
    for s in range(2):
        plt.figure()
        D = np.sqrt(A.isel(time=t, step=s).u10**2 + A.isel(time=t, step=s).v10**2)
        D.plot(cmap='RdBu', vmin=-25, vmax=25)
        plt.show()
        