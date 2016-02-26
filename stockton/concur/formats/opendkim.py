"""
config for opendkim, locations are for Ubuntu 14.04
"""

from . import generic


class OpenDKIM(generic.SpaceConfig):
    dest_path = "/etc/opendkim.conf"

