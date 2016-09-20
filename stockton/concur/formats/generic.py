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
            name.ljust(max(self.config.option_buffer, len(name) + 1), " "),
            val
        )
        return s


class SpaceConfig(base.Config):
    """Configuration files that have a format like

    name            val

    type of configuration
    """
    option_divider = "\s"
    option_buffer = 24
    option_class = SpaceOption

