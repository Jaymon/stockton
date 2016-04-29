"""
Generic starter config parsers for a variety of different file formats

https://en.wikipedia.org/wiki/Configuration_file
http://stackoverflow.com/questions/1925305/best-config-file-format

"""
import re

import base


class EqualOption(base.ConfigOption):
    def format_set(self, name, divider, val):
        option_set_format = "{} {} {}" # key = val
        s = option_set_format.format(name, divider, val)
        return s


class EqualConfig(base.Config):
    """Configuration files that have a format like

    name = val

    type of configuration
    """
    option_divider = "="
    option_class = EqualOption


class ColonOption(base.ConfigOption):
    def format_set(self, name, divider, val):
        option_set_format = "{}{} {}" # key: val
        s = option_set_format.format(name, divider, val)
        return s


class ColonConfig(base.Config):
    """Configuration files that have a format like

    name: val

    type of configuration
    """
    option_divider = ":"
    option_class = ColonOption


class SpaceOption(base.ConfigOption):
    def format_set(self, name, divider, val):
        option_set_format = "{}{}" # key val
        s = option_set_format.format(
            name.ljust(max(self.config.option_buffer, len(name) + 1), divider),
            val
        )
        return s

    def _parse(self, fp):
        line = fp.line
        name = ""
        val = ""
        comment = ""
        commenters = self.config.commenters
        divider = self.config.option_divider

        if re.match("^[^{}]\S+".format(commenters), line): # name val
            name, val = re.split("\s+", line, 1)

        elif re.match("^[{}]\s*\S+\s*{}".format(commenters, divider), line): # # name val
            l = re.sub("^[{}]\s*".format(commenters), "", line)
            name, val = re.split("\s+", l, 1)

        #elif re.match("^[{}]".format(commenters)):

        bits = re.split("\s[{}]\s*".format(commenters), val, 1)
        val = bits[0]
        if len(bits) > 1:
            comment = bits[1]

        self.name = name
        self.val = val
        self.comment = comment
        self.line = line
        self.modified = False


class SpaceConfig(base.Config):
    """Configuration files that have a format like

    name            val

    type of configuration
    """
    option_divider = " "
    option_buffer = 24
    option_class = SpaceOption

