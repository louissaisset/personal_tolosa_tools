import numpy as np
from astropy.convolution import Gaussian2DKernel, convolve_fft
reso_ini = 1000
x = np.linspace(-10, 10, reso_ini)
y = np.linspace(-10, 10, reso_ini)
X, Y = np.meshgrid(x, y)

# # Version 0
# mnt_in = np.ones(X.shape)
# mnt_in[np.sqrt(X**2 + Y**2) < 5] = 0
# mnt_in[np.sqrt(X**2 + Y**2) < 4] = 1
# mnt_in[np.sqrt(X**2 + Y**2) < 3] = 0
# mnt_in[np.sqrt(X**2 + Y**2) < 2] = 1

# mask = np.zeros(X.shape)
# mask[np.logical_and(np.abs(Y)<1, np.abs(X-2)<2)] = 1


# # Version 1
# mnt_in = np.random.random(X.shape)
# mnt_in[np.logical_and(np.abs(X-Y) < 1, 
#                       np.abs(X) < 3.5)] = 10
    
# mask = np.zeros(X.shape)
# mask[np.logical_and(np.abs(X-Y) < 1, 
#                     np.abs(X) < 3.5)] = 1


# Version 2
factor = 40
x0 = np.linspace(-10, 10, reso_ini//factor)
y0 = np.linspace(-10, 10, reso_ini//factor)
X0, Y0 = np.meshgrid(x0, y0)

mnt_in_0 = np.random.random(X0.shape)
mnt_in_0[np.logical_and(np.abs(X0-Y0) < 1, 
                        np.abs(X0) < 3.5)] = 10
mnt_in = np.zeros(X.shape)
for i in range(factor):
    for j in range(factor):
        mnt_in[i::factor, j::factor] = mnt_in_0

mask = np.zeros(X.shape)
mask[np.logical_and(np.abs(X-Y) < 1, 
                    np.abs(X) < 3.5)] = 1



std_dev = 20

kernel = Gaussian2DKernel(std_dev)

# Size of the tile - Avoid to use a too large memory in the convolution process
size_window = 1000
overlap     = 4 * int(std_dev)
mnt_out = np.copy(mnt_in)
j = 0
while j <= mnt_in.shape[0]-1:
    i = 0
    while i <= mnt_in.shape[1]-1:
        i1 = max( 0 , i-overlap )
        i2 = min( mnt_in.shape[1]-1, i+size_window-1+overlap )
        j1 = max( 0 , j-overlap )
        j2 = min( mnt_in.shape[0]-1, j+size_window-1+overlap )

        tmp = convolve_fft(mnt_in[j1:j2+1,i1:i2+1], 
                           kernel, 
                           nan_treatment='interpolate',
                           mask = mask[j1:j2+1,i1:i2+1])

        ii1 = i-i1
        ii2 = min(mnt_in.shape[1]-1,i+size_window-1)-i+ii1
        jj1 = j-j1
        jj2 = min(mnt_in.shape[0]-1,j+size_window-1)-j+jj1

        i1 = max(0,i)
        i2 = min(mnt_in.shape[1]-1,i+size_window-1)
        j1 = max(0,j)
        j2 = min(mnt_in.shape[0]-1,j+size_window-1)

        mnt_out[j1:j2+1,i1:i2+1] = tmp[jj1:jj2+1,ii1:ii2+1]

        i = i + size_window
    j = j + size_window

resu = mnt_in * mask + mnt_out * (1-mask)

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
plt.rcParams["font.size"] = 8
plt.rcParams["font.family"] = "cmr10"
plt.rcParams['text.usetex'] = True
plt.rcParams['axes.formatter.use_mathtext'] = True
plt.rcParams['mathtext.fontset'] = "custom"
plt.rcParams['mathtext.rm'] = "cmr10"
plt.rcParams['mathtext.it'] = "cmr10:italic"
plt.rcParams['mathtext.bf'] = "cmr10:bold"
    
# Create a figure
fig, ax0 = plt.subplots(1, 1, figsize=(2.5, 2.5))

# Create axes and plot Z0, Z1, Z2, Z3 using pcolor
p0 = ax0.pcolor(X, Y, mnt_out, shading='auto', cmap='jet', vmin=0, vmax=10)
ax0.set_title('Smoothed values')
ax0.tick_params(labelbottom=True, labelleft=True, direction='in')
ax0.set_yticklabels(ax0.get_yticks(), rotation=90, verticalalignment='center')
ax0.set_aspect('equal')

ax1 = fig.add_axes([ax0.get_position().x1 + 0.11, ax0.get_position().y0, 
                    ax0.get_position().width, ax0.get_position().height])
p1 = ax1.pcolor(X, Y, resu, shading='auto', cmap='jet', vmin=0, vmax=10)
ax1.set_title('Result')
ax1.tick_params(labelbottom=True, labelleft=False, direction='in')
ax1.set_aspect('equal')

ax2 = fig.add_axes([ax0.get_position().x0, ax0.get_position().y1 + 0.11, 
                    ax0.get_position().width, ax0.get_position().height])
p2 = ax2.pcolor(X, Y, mnt_in, shading='auto', cmap='jet', vmin=0, vmax=10)
ax2.set_title('Initial MNT')
ax2.tick_params(labelbottom=False, labelleft=True, direction='in')
ax2.set_yticklabels(ax2.get_yticks(), rotation=90, verticalalignment='center')
ax2.set_aspect('equal')

ax3 = fig.add_axes([ax0.get_position().x1 + 0.11, ax0.get_position().y1 + 0.11, 
                    ax0.get_position().width, ax0.get_position().height])
p3 = ax3.pcolor(X, Y, mask, shading='auto', cmap='Greys', vmin=0, vmax=1)
ax3.set_title('Mask')
ax3.tick_params(labelbottom=False, labelleft=False, direction='in')
ax3.set_aspect('equal')

# Create axes for the colorbars on the right side
cax0 = fig.add_axes([ax1.get_position().x1 + 0.11, ax1.get_position().y0, 
                     0.05, ax1.get_position().height])  # for Z1 colorbar
cbar0 = fig.colorbar(p1, cax=cax0)
cbar0.set_label('Depths')
cbar0.ax.tick_params(rotation=90)
cax0.set_yticklabels(cbar0.get_ticks(), verticalalignment='center')
cax0.yaxis.set_major_formatter(FormatStrFormatter('%.0f'))

cax1 = fig.add_axes([ax3.get_position().x1 + 0.11, ax3.get_position().y0, 
                     0.05, ax1.get_position().height])  # for Z3 colorbar
cbar1 = fig.colorbar(p3, cax=cax1)
cbar1.set_label('Mask values')
cbar1.ax.tick_params(rotation=90)
cax1.set_yticklabels(cbar1.get_ticks(), verticalalignment='center')
cax1.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

plt.show()