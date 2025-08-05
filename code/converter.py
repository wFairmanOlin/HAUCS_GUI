import math
import numpy as np
from scipy.optimize import curve_fit
import logging
logger = logging.getLogger(__name__)

def to_fahrenheit(temp):
    return (temp / 5) * 9 + 32

def to_celcius(temp):
    return ((temp - 32) / 9) * 5

def convert_raw_to_mgl(do, t, p=977, s=0):
    '''
    do: dissolved oxygen as ratio (1 = 100% saturation)
    t: temperature in celcius
    p: pressure in hPa, default is pressure at 400ft
    s: salinity in parts per thousand
    '''
    T = t + 273.15 #temperature in kelvin
    P = p * 9.869233e-4 #pressure in atm

    #Handle Arrays
    if isinstance(do, list):
        do = np.array(do)


    DO_baseline = math.exp(-139.34411 + 1.575701e5/T - 6.642308e7/math.pow(T, 2) + 1.2438e10/math.pow(T, 3) - 8.621949e11/math.pow(T, 4))
    # SALINITY CORRECTION
    Fs = math.exp(-s * (0.017674 - 10.754/T + 2140.7/math.pow(T, 2)))
    # PRESSURE CORRECTION
    theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * math.pow(t, 2)
    u = math.exp(11.8571 - 3840.7/T - 216961/math.pow(T, 2))
    Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

    DO_corrected = DO_baseline * Fs * Fp

    DO_mgl = do * DO_corrected

    return DO_mgl

def convert_mgl_to_raw(do, t, p=977, s=0):
    '''
    do: dissolved oxygen as ratio (1 = 100% saturation)
    t: temperature in celcius
    p: pressure in hPa, default is pressure at 400ft
    s: salinity in parts per thousand
    '''
    T = t + 273.15 #temperature in kelvin
    P = p * 9.869233e-4 #pressure in atm

    #Handle Arrays
    if isinstance(do, list):
        do = np.array(do)

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

def exp_func(x, a, b, c):
    return a * np.exp(-b * x) + c

def calculate_do_fit(do_vals, max_time=30, sample_hz=1):
    '''
    do_vals:   array of DO values (either mgl or percent sat)
    max_time:  max time where DO values are still valid
    sample_hz: samle frequency used to collect do_vals

    return:
    popt: optimization parameters for either curve fit or linear fit
    fit_type: "curve" for curve fit or "linear" for linear fit
    '''

    do_vals = np.array(do_vals)
    
    time = np.arange(len(do_vals)) / sample_hz

    #trim time and do vals to be less than max time
    time = time[time <= max_time]
    do_vals = do_vals[: len(time)]

    x_plot = np.linspace(0, max_time, max_time * 10)
    y_fit = np.zeros_like(x_plot)

    try:
        popt, _ = curve_fit(exp_func, time, do_vals)
        fit_type = "curve"

    except Exception as e:
        logger.info("curve fit failed, defaulting to line of best fit")

        popt = np.polyfit(time, do_vals, 1)
        fit_type = "linear"

    return popt, fit_type


def generate_do(x, popt, fit_type):
    '''
    x: input in seconds (array or scalar)
    popt: output from calculate_do_fit
    fit_type: output from calculate_do_fit

    return: DO array of len x
    '''
    if fit_type == "curve":
        y = exp_func(x, *popt)
    else:
        y = np.polyval(popt, x)

    return y


def pressure_to_depth(p, init_p):
    '''
    p: pressure at depth measurment
    init_p: ambient air pressure
    '''
    return round(10.197 / 25.4 * (p - init_p), 1)