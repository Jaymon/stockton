"""
Postfix specific configuration files, the file locations are for ubuntu 14.04
"""
#import re

from . import generic
from . import base


class SpamAssassinOption(base.ConfigOption):
    def format_set(self, name, divider, val):
        option_set_format = "{}{}{}" # key=val
        s = option_set_format.format(name, divider, val)
        return s


class SpamAssassin(generic.EqualConfig):
    option_class = SpamAssassinOption
    dest_path = "/etc/default/spamassassin"


class Local(generic.SpaceConfig):
    dest_path = "/etc/spamassassin/local.cf"

