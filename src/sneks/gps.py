from decimal import Decimal
from math import radians, degrees, cos, sin, asin, sqrt, fabs, log, tan, pi, atan2

def bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    startLat, startLong, endLat, endLong = map(radians, [lat1, lon1, lat2, lon2])
    dPhi = log(tan(endLat/2.0+pi/4.0)/tan(startLat/2.0+pi/4.0))
    if abs(dLong) > pi:
        if dLong > 0.0:
            dLong = -(2.0 * pi - dLong)
        else:
            dLong = (2.0 * pi + dLong)
    bearing = (degrees(atan2(dLong, dPhi)) + 360.0) % 360.0
    return bearing

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    # https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000 # Radius of earth in meters. Use 3959 for miles or 20903520 for feet
    return c * r

def minimize_gps(point, distance=1):
    latitude = point["lat"]
    longitude = point["lng"]
    lat_str = str(latitude)
    lng_str = str(longitude)
    _lat_str = lat_str
    _lng_str = lng_str
    while haversine(latitude, longitude, float(_lat_str), float(_lng_str)) < distance:
        lat_str = _lat_str
        lng_str = _lng_str
        if len(_lat_str.split(".")[1]) >= len(_lng_str.split(".")[1]):
            _lat_str = _lat_str[:-1]
        if len(_lat_str.split(".")[1]) <= len(_lng_str.split(".")[1]):
            _lng_str = _lng_str[:-1]
    return {"lat":Decimal(lat_str), "lng":Decimal(lng_str)}
