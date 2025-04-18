#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 10:52:50 2025

@author: llsaisset
"""

import numpy as np 
import matplotlib.pyplot as plt


def soliton(x, t, eta_0=1, h_0=10):
    c_0 = np.sqrt(9.81*h_0)
    c = c_0 * (1 + eta_0/(2*h_0))
    eta = eta_0 / np.cosh( 1 / ( 2 * h_0 ) * np.sqrt( 3 * eta_0 / h_0 ) * ( x - c * t ) )**2
    return eta


t = np.arange(500)
x = 1700

eta_0 = range(1, 10)
c_0 = range(1, 10)
h_0 = range(10, 100, 10)

ref_eta_0 = eta_0[0]
ref_h_0 = h_0[2]

plt.figure()
for eta_ele in eta_0:
    plt.plot(t, soliton(x, t, eta_ele, ref_h_0))
plt.show()

plt.figure()
for h_ele in h_0:
    plt.plot(t, soliton(x, t, ref_eta_0, h_ele))
plt.show()
