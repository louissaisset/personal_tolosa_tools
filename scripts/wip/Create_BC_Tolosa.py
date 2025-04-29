#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 10:52:50 2025

@author: llsaisset
"""

import numpy as np 
import matplotlib.pyplot as plt
import os

def soliton(x, t, eta_0=1, h_0=10, S=3*10**4):
    """Calculate water flow (q) for a soliton wave"""
    g = 9.81  # gravitational acceleration (m/s²)
    c_0 = np.sqrt(g * h_0)  # shallow water wave speed
    c = c_0 * (1 + eta_0 / (2 * h_0))  # actual wave speed
    
    # Calculate water elevation first
    eta = eta_0 / np.cosh(1 / (2 * h_0) * np.sqrt(3 * eta_0 / h_0) * (x - c * t))**2
    
    # Convert water elevation to water flow
    q = S*(eta * c - (h_0 + eta) * eta * c_0**2 / (2 * g * h_0))
    return eta, q

def main():
    # Parameters
    eta_0 = 1                    # wave amplitude (m)
    h_0 = 30.0                   # initial water depth (m)
    t = np.arange(0, 3600)       # time range (s)
    x = 1500                     # spatial lag (m)

    filename = "bc_ocean.txt"
    
    # Calculate water elevation and flow
    eta, q = soliton(x, t, eta_0, h_0)
    
    with open(os.path.join('.',  filename), 'w') as file:
        file.write("$ q(t)\n")
        for ti, qi in zip(t, q):
            file.write(f"{ti}. {qi:.4f}\n")
    
if __name__ == "__main__":
    exit(main())
