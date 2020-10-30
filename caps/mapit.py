from requests_cache import CachedSession
from django.conf import settings

session = CachedSession(cache_name=settings.CACHE_FILE, expire_after=86400)

class BaseException(Exception):
    pass

class NotFoundException(BaseException):
    pass

class BadRequestException(BaseException):
    pass

class MapIt(object):
    postcode_url = '%s/postcode/%s'
    cache = {}

    def __init__(self):
        self.base = settings.MAPIT_URL


    def postcode_point_to_gss_codes(self, pc):
        url = self.postcode_url % (self.base, pc)
        data = self.get(url)
        gss_codes = []
        for area in data['areas'].values():
            if 'gss' in area['codes']:
                gss_codes.append(area['codes']['gss'])
        return gss_codes

    def get(self, url):
        if url not in self.cache:
            resp = session.get(url)
            data = resp.json()
            if resp.status_code == 404:
                raise NotFoundException(data['error'])
            if resp.status_code == 400:
                raise BadRequestException(data['error'])
            self.cache[url] = data
        return self.cache[url]
