from requests_cache import CachedSession
from django.conf import settings

session = CachedSession(cache_name=settings.CACHE_FILE, expire_after=86400)


class BaseException(Exception):
    pass


class NotFoundException(BaseException):
    pass


class BadRequestException(BaseException):
    pass


class InternalServerErrorException(BaseException):
    pass


class ForbiddenException(BaseException):
    pass


class MapIt(object):
    postcode_url = "%s/postcode/%s?api_key=%s"
    gss_code_url = "%s/code/gss/%s?api_key=%s"
    # From https://mapit.mysociety.org/docs/#api-multiple_areas
    # CTY (county council)
    # COI (Isles of Scilly)
    # DIS (district council)
    # LBO (London borough)
    # LGD (NI council)
    # MTD (Metropolitan district)
    # UTA (Unitary authority)
    touches_url = "%s/area/%s/intersects?type=CTY,COI,DIS,LBO,LGD,MTD,UTA&api_key=%s"
    wgs84_url = "%s/point/4326/%s,%s&api_key=%s"
    cache = {}

    def __init__(self):
        self.base = settings.MAPIT_URL

    def gss_code_to_mapit_id(self, gss_code):
        url = self.gss_code_url % (self.base, gss_code, settings.MAPIT_API_KEY)
        data = self.get(url)
        return data["id"]

    def mapit_id_to_touches(self, mapit_id):
        url = self.touches_url % (self.base, mapit_id, settings.MAPIT_API_KEY)
        data = self.get(url)
        gss_codes = []
        for area in data.values():
            if area["codes"].get("gss"):
                gss_codes.append(area["codes"]["gss"])
        return gss_codes

    def postcode_point_to_gss_codes(self, pc):
        url = self.postcode_url % (self.base, pc, settings.MAPIT_API_KEY)
        data = self.get(url)
        gss_codes = []
        for area in data["areas"].values():
            if "gss" in area["codes"]:
                gss_codes.append(area["codes"]["gss"])
        return gss_codes

    def wgs84_point_to_gss_codes(self, lon, lat):
        url = self.wgs84_url % (self.base, lon, lat, settings.MAPIT_API_KEY)
        data = self.get(url)
        gss_codes = []
        for area in data.values():
            if "gss" in area["codes"]:
                gss_codes.append(area["codes"]["gss"])
        return gss_codes

    def get(self, url):
        if url not in self.cache:
            resp = session.get(url)
            data = resp.json()
            if resp.status_code == 403:
                raise ForbiddenException(data["error"])
            if resp.status_code == 500:
                raise InternalServerErrorException(data["error"])
            if resp.status_code == 404:
                raise NotFoundException(data["error"])
            if resp.status_code == 400:
                raise BadRequestException(data["error"])
            self.cache[url] = data
        return self.cache[url]
