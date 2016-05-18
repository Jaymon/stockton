"""
Geo support 
"""
import tempfile
import urllib
import gzip
import os

import geoip2.database

from . import cli


class IP(str):
    @property
    def geo_ip(self):
        if not os.path.isfile(self.geo_path):
            self.download_geo()

        if not hasattr(self, "_geo_ip"):
            cls = type(self)
            if not hasattr(cls, "geo_db"):
                type(self).geo_db = geoip2.database.Reader(self.geo_path)
            self._geo_ip = cls.geo_db.city(self)

        return self._geo_ip

    @property
    def country(self):
        return self.geo_ip.country.iso_code

    @property
    def state(self):
        return self.geo_ip.subdivisions.most_specific.iso_code

    @property
    def city(self):
        return self.geo_ip.city.name

    def __new__(cls, ip_addr=""):
        if not ip_addr:
            ip_addr = cli.ip()
        instance = super(IP, cls).__new__(cls, ip_addr)
        instance.geo_path = os.path.join(tempfile.gettempdir(), "GeoLite2-City.mmdb")
        instance.geo_url = "http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz"
        return instance

    def download_geo(self):
        gz_path = "{}.gz".format(self.geo_path)
        # http://stackoverflow.com/a/31857152/5006
        urllib.urlretrieve(self.geo_url, gz_path)

        # TODO -- see if this works
        # https://docs.python.org/2/library/gzip.html
#         with open('file.txt', 'rb') as f_in, gzip.open('file.txt.gz', 'wb') as f_out:
#             shutil.copyfileobj(f_in, f_out)

        with gzip.open(gz_path, 'rb') as gzf:
            with open(self.geo_path, "wb") as f:
                f.write(gzf.read())


