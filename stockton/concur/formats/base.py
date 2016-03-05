"""
The base classes for all the other formats,

usually, you would actually use the classes in generics.py as the start for your custom
configuration parser, the classes in this module are the support classes for the
generics
"""
import re
from collections import defaultdict


class ConfigBase(object):
    """the base common class for most of the other more useful classes"""
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.sections = defaultdict(list)
        self.options = defaultdict(list)
        self.lines = []
        self.name = ""
        self.val = ""

    def parse(self, fp):
        self.line = fp.line
        self._parse(fp)
        self.modified = False

    def is_valid(self):
        return True

    def update(self, *args, **kwargs):
        for k, v in args:
            self[k] = v

        for k, v in kwargs.items():
            self[k] = v

    def __setattr__(self, k, v):
        # http://stackoverflow.com/questions/17576009/python-class-property-use-setter-but-evade-getter
        if k == "modified":
            self.__dict__["modified"] = v

        else:
            self.modified = True
            super(ConfigBase, self).__setattr__(k, v)

    def __missing__(self, k):
        try:
            # we are either a section or the config option, assume we are a
            # section, fallback to being the config
            option = self.config.create_option()
        except AttributeError:
            option = self.create_option()

        option.name = k
        self.options[option.name].append(len(self.lines))
        self.lines.append(option)
        return option

    def __contains__(self, k):
        return k in self.sections or k in self.options

    def __getitem__(self, k):
        line_numbers = []
        if k in self.sections:
            line_numbers = self.sections[k]

        elif k in self.options:
            line_numbers = self.options[k]

        if len(line_numbers) == 1:
            v = self.lines[line_numbers[0]]

        elif len(line_numbers) > 1:
            v = [self.lines[ln] for ln in line_numbers]

        else:
            v = self.__missing__(k)
            #raise KeyError("no section or option {}".format(k))

        return v

    def __setitem__(self, k, v):
        if k in self.sections:
            raise ValueError("you cannot modify sections using dict notation")

        line_numbers = []

        if k in self.options:
            line_numbers = self.options[k]

        if len(line_numbers) > 0:
            for line_number in line_numbers:
                option = self.lines[line_number]
                option.val = v

        else:
            option = self.__missing__(k)
            option.val = v


class ConfigLine(ConfigBase):
    def __str__(self):
        return self.line

    def _parse(self, fp):
        self.line = fp.line


class ConfigOption(ConfigLine):
    def is_valid(self):
        return bool(self.name)

    def _parse(self, fp):
        line = fp.line
        name = ""
        val = ""
        comment = ""
        commenters = self.config.commenters
        divider = self.config.option_divider

        if re.match("^[^{}]\S+".format(commenters), line): # name = val
            name, val = re.split("\s*{}\s*".format(divider), line, 2)

        elif re.match("^[{}]\s*\S+\s*{}".format(commenters, divider), line): # # name = val
            l = re.sub("^[{}]\s*".format(commenters), "", line)
            name, val = re.split("\s*{}\s*".format(divider), l, 2)

        bits = re.split("\s[{}]\s*".format(commenters), val, 2)
        val = bits[0]
        if len(bits) > 1:
            comment = bits[1]

        self.name = name
        self.val = val
        self.comment = comment
        self.line = line
        self.modified = False

    def __str__(self):
        s = ""
        if self.modified:
            s = self.format_set(
                self.name,
                self.config.option_divider,
                self.val
            )
            comment = getattr(self, "comment", "")
            if comment:
                s += " {} {}".format(self.commenters[0], comment)

        else:
            s = super(ConfigOption, self).__str__()

        return s

    def format_set(self, name, divider, val):
        option_set_format = "{} {} {}" # key, divider, val
        s = option_set_format.format(name, divider, val)
        return s


class ConfigSection(ConfigOption):
    def _parse(self, fp):
        pass

    def __str__(self):
        s = "\n".join(str(cl) for cl in self.lines)
        return s


class ConfigFile(object):
    def __init__(self, path, config):
        self.path = path
        self.config = config
        # we load the whole config file into memory because we hate memory and to
        # punish it we like to use lots of it. Also, we were having some difficulty
        # getting some conf files to parse correctly without being able to seek and
        # stuff to certain lines and replay parts of the file and this was the 
        # easiest solution to that problem
        with open(self.path, "r") as fp:
            self.lines = fp.readlines()
            self.count = len(self.lines)

        self.line_number = -1

    def close(self):
        if not self.fp.closed:
            self.fp.close()

    def __iter__(self):
        return self

    def __count__(self):
        return self.count

    def rewind(self, line_number):
        self.line_number = line_number

    def next(self):
        self.line_number += 1
        if self.line_number >= self.count:
            raise StopIteration()

        self.line = self.lines[self.line_number].rstrip()

        c = self.config.create_section()
        c.parse(self)
        if not c.is_valid():
            c = self.config.create_option()
            c.parse(self)
            if not c.is_valid():
                c = self.config.create_line()
                c.parse(self)

        return c


class Config(ConfigBase):
    """config parser that allows you to modify the parsed file and write it back out

    we don't use shlex because it didn't preserve comments
    https://docs.python.org/2/library/shlex.html 

    If an ini specific parser is added at a later date, use this?
    https://docs.python.org/2/library/configparser.html
    """

    commenters = "#"

    option_divider = "="

    line_class = ConfigLine

    option_class = ConfigOption

    section_class = ConfigSection

    file_class = ConfigFile


    dest_path = ""

    prototype_path = ""

    def __init__(self, dest_path="", prototype_path=""):
        self.reset()

        if prototype_path:
            self.prototype_path = prototype_path
            self.parse()

        if dest_path:
            self.dest_path = dest_path

    def create_line(self):
        return self.line_class(self)

    def create_option(self):
        return self.option_class(self)

    def create_section(self):
        return self.section_class(self)

    def create_file(self):
        return self.file_class(self.prototype_path, self)

    def parse(self):
        fp = self.create_file()
        self.reset()

        for line_number, c in enumerate(fp):
            if isinstance(c, self.section_class):
                self.sections[c.name].append(line_number)
                self.lines.append(c)

            elif isinstance(c, self.option_class):
                self.options[c.name].append(line_number)
                self.lines.append(c)
 
            elif isinstance(c, self.line_class):
                self.lines.append(c)

    def __str__(self):
        return "\n".join((str(cl) for cl in self))

    def __iter__(self):
        for cl in self.lines:
            yield cl

    def save(self):
        with open(self.dest_path, "w") as f:
            for cl in self:
                f.write(str(cl))
                f.write("\n")

