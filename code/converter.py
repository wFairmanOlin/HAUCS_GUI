import math
import numpy as np

def to_fahrenheit(temp):
    return (temp / 5) * 9 + 32

def to_celcius(temp):
    return ((temp - 32) / 9) * 5

def convert_percent_to_mgl(do, t, p, s=0):
    '''
    do: dissolved oxygen in percent saturation
    t: temperature in celcius
    p: pressure in hPa
    s: salinity in parts per thousand
    '''
    T = t + 273.15 #temperature in kelvin
    P = p * 9.869233e-4 #pressure in atm

    DO_baseline = math.exp(-139.34411 + 1.575701e5/T - 6.642308e7/math.pow(T, 2) + 1.2438e10/math.pow(T, 3) - 8.621949e11/math.pow(T, 4))
    # SALINITY CORRECTION
    Fs = math.exp(-s * (0.017674 - 10.754/T + 2140.7/math.pow(T, 2)))
    # PRESSURE CORRECTION
    theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * math.pow(t, 2)
    u = math.exp(11.8571 - 3840.7/T - 216961/math.pow(T, 2))
    Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

    DO_corrected = DO_baseline * Fs * Fp

    DO_mgl = do / 100 * DO_corrected

    return DO_mgl

def convert_mgl_to_percent(do, t, p, s=0):
    '''
    do: dissolved oxygen in percent saturation
    t: temperature in celcius
    p: pressure in hPa
    s: salinity in parts per thousand
    '''
    T = t + 273.15 #temperature in kelvin
    P = p * 9.869233e-4 #pressure in atm

    DO_baseline = math.exp(-139.34411 + 1.575701e5/T - 6.642308e7/math.pow(T, 2) + 1.2438e10/math.pow(T, 3) - 8.621949e11/math.pow(T, 4))
    # SALINITY CORRECTION
    Fs = math.exp(-s * (0.017674 - 10.754/T + 2140.7/math.pow(T, 2)))
    # PRESSURE CORRECTION
    theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * math.pow(t, 2)
    u = math.exp(11.8571 - 3840.7/T - 216961/math.pow(T, 2))
    Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

    DO_corrected = DO_baseline * Fs * Fp

    DO_percent = do / DO_corrected

    return DO_percent