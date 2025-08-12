import pickle
import time

def load_pickle(filepath):
    with open(filepath, 'rb') as file:
        sdata = pickle.load(file)
    return sdata