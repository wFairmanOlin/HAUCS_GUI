import math
import numpy as np
from scipy.optimize import curve_fit

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


def calculate_do_and_fit(do_vals, max_time= 30):
    
    def exp_func(x, a, b, c):
        return a * np.exp(-b * x) + c
    
    do_vals = [100 * i for i in do_vals] #CONVERT TO PERCENT SATURATION
    s_time = np.arange(len(do_vals)) #TODO: This only works with a sampling rate of 1 hz

    x_plot = np.linspace(0, max_time, max_time * 10)

    # default fallback
    y_fit = np.zeros_like(x_plot)
    y_at_30 = None

    print(f"do vals\n{do_vals}\ns_time\n{s_time}\nx_plot\n{x_plot}")

    try:
        popt, _ = curve_fit(exp_func, s_time, do_vals)
        y_fit = exp_func(x_plot, *popt)
        y_at_30 = exp_func(30, *popt)

    except Exception as e:
        print("Curve fit failed:", e)

        p = np.polyfit(s_time, do_vals, 1)
        y_fit = np.polyval(p, x_plot)
        y_at_30 = np.polyval(p, 30)
    
    if y_at_30 < 0:
        print("oops broke physics, predicted DO below 0%")
        y_at_30 = 0

    print(f"converter y-fit\n{y_fit}")
    return y_fit, x_plot, y_at_30, do_vals, s_time
