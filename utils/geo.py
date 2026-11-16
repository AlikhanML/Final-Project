"""Geographic calculations; coordinates are (latitude, longitude)."""
import numpy as np

def distance(a, b):
    """Haversine: метр, географиялық координаттар (lat, lon)."""
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    h = sin((lat2-lat1)/2)**2+cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return 6371000*2*asin(sqrt(min(1.,max(0.,h))))



def to_latlon(world,xy):
    return np.column_stack([xy[:,1]/111320+world['lat0'],xy[:,0]/(111320*np.cos(np.radians(world['lat0'])))+world['lon0']])

