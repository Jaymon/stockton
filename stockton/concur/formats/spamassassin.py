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
    option_name_regexes = [
        "^score\s+[A-Z0-9_]+"
    ]

    def update_option(self, option, v):
        if option.name == "loadplugin":
            ret = False
            if option.val == v:
                option.val = v
                ret = True

        else:
            ret = super(Local, self).update_option(option, v)

        return ret

