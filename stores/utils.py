from math import atan2, cos, radians, sin, sqrt


def _to_float(value):
    if value in (None, ''):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_geo_search_state(request):
    latitude = _to_float(request.session.get('search_latitude'))
    longitude = _to_float(request.session.get('search_longitude'))
    radius_km = _to_float(request.session.get('search_radius_km'))

    return {
        'latitude': latitude,
        'longitude': longitude,
        'radius_km': radius_km,
        'has_location': latitude is not None and longitude is not None,
        'has_radius': radius_km is not None,
        'radius_label': 'Ninguno' if radius_km is None else f'{radius_km:g} km',
    }


def haversine_distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    earth_radius_km = 6371.0

    lat_a = radians(latitude_a)
    lon_a = radians(longitude_a)
    lat_b = radians(latitude_b)
    lon_b = radians(longitude_b)

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a

    a = sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    return earth_radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def store_is_within_radius(store, latitude, longitude, radius_km):
    if latitude is None or longitude is None or radius_km is None:
        return True

    if store.latitud is None or store.longitud is None:
        return False

    distance = haversine_distance_km(latitude, longitude, float(store.latitud), float(store.longitud))
    return distance <= radius_km


def filter_stores_by_geo(queryset, geo_state):
    if not geo_state.get('has_location') or not geo_state.get('has_radius'):
        return queryset

    latitude = geo_state['latitude']
    longitude = geo_state['longitude']
    radius_km = geo_state['radius_km']

    store_ids = []
    for store in queryset.only('id', 'latitud', 'longitud'):
        if store_is_within_radius(store, latitude, longitude, radius_km):
            store_ids.append(store.pk)

    return queryset.filter(pk__in=store_ids)


def filter_products_by_geo(queryset, geo_state):
    if not geo_state.get('has_location') or not geo_state.get('has_radius'):
        return queryset

    latitude = geo_state['latitude']
    longitude = geo_state['longitude']
    radius_km = geo_state['radius_km']

    store_ids = []
    store_model = queryset.model._meta.get_field('tienda').remote_field.model
    store_cache = store_model.objects.only('id', 'latitud', 'longitud')
    for store in store_cache:
        if store_is_within_radius(store, latitude, longitude, radius_km):
            store_ids.append(store.pk)

    return queryset.filter(tienda_id__in=store_ids)