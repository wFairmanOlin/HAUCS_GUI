import math
import numpy as np

def to_fahrenheit(temp):
    return (temp / 5) * 9 + 32

def to_celcius(temp):
    return ((temp - 32) / 9) * 5

# def convert_percent_to_mgl(do, t, p, s=0):
#     '''
#     do: dissolved oxygen in percent saturation
#     t: temperature in celcius
#     p: pressure in hPa
#     s: salinity in parts per thousand
#     '''
#     T = t + 273.15 #temperature in kelvin
#     P = p * 9.869233e-4 #pressure in atm

#     DO_baseline = math.exp(-139.34411 + 1.575701e5/T - 6.642308e7/math.pow(T, 2) + 1.2438e10/math.pow(T, 3) - 8.621949e11/math.pow(T, 4))
#     # SALINITY CORRECTION
#     Fs = math.exp(-s * (0.017674 - 10.754/T + 2140.7/math.pow(T, 2)))
#     # PRESSURE CORRECTION
#     theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * math.pow(t, 2)
#     u = math.exp(11.8571 - 3840.7/T - 216961/math.pow(T, 2))
#     Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

#     DO_corrected = DO_baseline * Fs * Fp

#     DO_mgl = do / 100 * DO_corrected

#     return DO_mgl

def convert_percent_to_mgl(do_percent, temp_c, pressure_hpa=1013.25, salinity=0):
    """
    Convert %DO saturation to mg/L using Weiss 1970 model (freshwater)
    Weiss, R. F. (1970).
    The solubility of oxygen in water and seawater.
    Deep Sea Research and Oceanographic Abstracts, 17(4), 721–735.
    https://doi.org/10.1016/0011-7471(70)90037-9
    """
    do_percent = do_percent * 100
    T = temp_c + 273.15  # Kelvin

    # Weiss 1970 coefficients for freshwater
    ln_DO = (-139.34411 +
             (157570.1 / T) -
             (66423080 / (T ** 2)) +
             (12438000000 / (T ** 3)) -
             (862194900000 / (T ** 4)))

    DO_sat_mgl = math.exp(ln_DO)

    # Apply % saturation
    DO_mgl = (do_percent / 100.0) * DO_sat_mgl

    return DO_mgl



# def convert_mgl_to_percent(do_mgl, t, p, s=0):
#     '''
#     do_mgl: dissolved oxygen in mg/L
#     t: temperature in Celsius
#     p: pressure in hPa
#     s: salinity in parts per thousand
#     '''
#     T = t + 273.15  # Temperature in Kelvin
#     P = p * 9.869233e-4  # Pressure in atm

#     # DO saturation baseline at 100% (mg/L)
#     DO_baseline = math.exp(
#         -139.34411 +
#         (1.575701e5 / T) -
#         (6.642308e7 / math.pow(T, 2)) +
#         (1.2438e10 / math.pow(T, 3)) -
#         (8.621949e11 / math.pow(T, 4))
#     )

#     # Salinity correction factor
#     Fs = math.exp(-s * (0.017674 - 10.754 / T + 2140.7 / math.pow(T, 2)))

#     # Pressure correction factor
#     theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * math.pow(t, 2)
#     u = math.exp(11.8571 - 3840.7 / T - 216961 / math.pow(T, 2))
#     Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

#     # Corrected 100% DO value
#     DO_corrected = DO_baseline * Fs * Fp

#     # Calculate DO in percent
#     do_percent = (do_mgl / DO_corrected) * 100

#     return do_percent

def convert_mgl_to_percent(do_mgl, temp_c, pressure_hpa=1013.25, salinity=0):
    T = temp_c + 273.15  # Kelvin

    ln_DO = (-139.34411 +
             (157570.1 / T) -
             (66423080 / (T ** 2)) +
             (12438000000 / (T ** 3)) -
             (862194900000 / (T ** 4)))

    DO_sat_mgl = math.exp(ln_DO)

    do_percent = (do_mgl / DO_sat_mgl)

    return do_percent
