"""
Generic starter config parsers for a variety of different file formats
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

        if not re.match("^[{}]\s+".format(commenters), line): # this could be a comment line
            if re.match("^[{}]?\S+".format(commenters), line): # name  val
                name, val = re.split("\s+", line, 2)
                name.lstrip(commenters)

            bits = re.split("\s[{}]\s*".format(commenters), val, 2)
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

