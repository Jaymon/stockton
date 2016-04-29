"""
The base classes for all the other formats,

usually, you would actually use the classes in generics.py as the start for your custom
configuration parser, the classes in this module are the support classes for the
generics
"""
import re
from collections import defaultdict
import itertools


class ConfigBase(object):
    """the base common class for most of the other more useful classes"""
    @property
    def factory(self):
        try:
            cls = self.config
            cls.option_class
        except AttributeError:
            cls = self
            cls.option_class
        return cls

    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.sections = defaultdict(list)
        self.options = defaultdict(list)

        # there are some things to keep in mind about lines, they don't have to be
        # true line numbers in the config file, they are line numbers in relation
        # to the content area you are in, so if the config file has 2 sections, then
        # there will only be 2 "lines" in that config file, one for each section
        self.lines = []

        self.name = ""
        self.val = ""

    def parse(self, fp):
        self.line = fp.line
        self._parse(fp)
        self.modified = False

    def is_valid(self):
        return True

    def create_option_for_key(self, k):
        """creates an option with name k, does not insert option into config file"""
        option = self.factory.create_option()
        option.name = k
        return option

    def update(self, *args, **kwargs):
        for body in itertools.chain(args, kwargs.items()):
            if isinstance(body, basestring):
                line = self.factory.create_line()
                line.line = body
                self.insert(len(self.lines), line)
            else:
                k, v = body
                self[k] = v

    def update_before(self, k, *args, **kwargs):
        """same as update but will insert all the args and kwargs before the option
        at k"""
        line_numbers = self.find_lines(k)
        if line_numbers:
            line_number = line_numbers[0] # the min line number you need to insert before
            for k, v in itertools.chain(args, kwargs.items()):
                if k in self:
                    self[k] = v

                else:
                    option = self.create_option_for_key(k)
                    option.val = v
                    self.insert(line_number, option)

        else:
            self.update(*args, **kwargs)

    def insert(self, line_number, option):
        """insert option before the given line_number, this is similar to the python
        built-in list.insert method, you need to use this function to keep all the
        internal data structurs in alignment"""
        if line_number < len(self.lines):
            # go through and move everything down to compensate for the
            # insert in the line_number list and line everything back up again
            for k in self.options.keys():
                k_line_numbers = self.options[k]
                for i in range(len(k_line_numbers)):
                    if k_line_numbers[i] > line_number:
                        k_line_numbers[i] += 1

            for k in self.sections.keys():
                k_line_numbers = self.sections[k]
                for i in range(len(k_line_numbers)):
                    if k_line_numbers[i] > line_number:
                        k_line_numbers[i] += 1

        self.lines.insert(line_number, option)
        if isinstance(option, self.factory.option_class):
            self.options[option.name].append(line_number)

        else:
            self.sections[option.name].append(line_number)

    def __setattr__(self, k, v):
        # http://stackoverflow.com/questions/17576009/python-class-property-use-setter-but-evade-getter
        if k == "modified":
            self.__dict__["modified"] = v

        else:
            self.modified = True
            super(ConfigBase, self).__setattr__(k, v)

    def __missing__(self, k):
        option = self.create_option_for_key(k)
        self.insert(len(self.lines), option)
        return option

    def __contains__(self, k):
        return k in self.sections or k in self.options

    def find_lines(self, k):
        """return how many lines the key is found in the config file"""
        line_numbers = []

        if k in self.sections:
            line_numbers = self.sections[k]

        elif k in self.options:
            line_numbers = self.options[k]

        return line_numbers

    def __getitem__(self, k):
        line_numbers = self.find_lines(k)

        # after we have the line count, we pull out that many lines, it's a string
        # if it is a one line value, or an array of lines if it encompassed more than
        # one line, if we didn't find the value at all, then create it
        if len(line_numbers) == 1:
            v = self.lines[line_numbers[0]]

        elif len(line_numbers) > 1:
            v = [self.lines[ln] for ln in line_numbers]

        else:
            v = self.__missing__(k)
            #raise KeyError("no section or option {}".format(k))

        return v

    def __setitem__(self, k, v):
        if isinstance(v, self.factory.section_class):
            if k in self.sections:
                self.sections[k] = v
            else:
                self.insert(len(self.lines), v)

        else:
            if k in self.sections:
                raise ValueError("you cannot modify sections using dict string notation")

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
    """This can be the base class for the different sections and options, or it
    can be a representation of a comment or some other line we don't usually do
    anything with"""
    def __str__(self):
        return self.line

    def _parse(self, fp):
        self.line = fp.line


class ConfigOption(ConfigLine):
    """This represents any key -> value pair in the configuration file"""
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
            name, val = re.split("\s*{}\s*".format(divider), line, 1)

        elif re.match("^[{}]\s*\S+\s*{}".format(commenters, divider), line): # # name = val
            l = re.sub("^[{}]\s*".format(commenters), "", line)
            name, val = re.split("\s*{}\s*".format(divider), l, 1)

        bits = re.split("\s[{}]\s*".format(commenters), val, 1)
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
    """certain configuration files might be broken up into sections of options, this
    handles representing those sections so when manipulating the config file you can
    add and rename sections, etc."""
    def _parse(self, fp):
        pass

    def __str__(self):
        s = "\n".join(str(cl) for cl in self.lines)
        return s


class ConfigFile(object):
    """This handles parsing the file internally"""
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


class ConfigBody(ConfigFile):
    def __init__(self, body, config):
        self.config = config
        self.lines = body.splitlines(False)
        self.count = len(self.lines)
        self.line_number = -1

    def close(self): pass


class Config(ConfigBase):
    """config parser that allows you to modify the parsed file and write it back out

    we don't use shlex because it didn't preserve comments
    https://docs.python.org/2/library/shlex.html 

    If an ini specific parser is added at a later date, use this?
    https://docs.python.org/2/library/configparser.html

    You can modify the config file in 3 different ways:

        1) item notation, config["option"] = "value"

            using the item notation, you set the value, either a string or list
            of strings

        2) update() notations, config.update([key, val], [key2, val2], ...)

            you send tuples of key, value pairs to the update method, the reason
            you pass in tuples is so order is preserved

        3) get item, for advanced manipulation of the option

            this is the only way to manipulate a section

            opt = config["option"]
            opt.val = "value"
    """

    commenters = "#"

    option_divider = "="

    line_class = ConfigLine

    option_class = ConfigOption

    section_class = ConfigSection

    file_class = ConfigFile

    body_class = ConfigBody

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

    def create_section(self, body=""):
        if body:
            config_s = self.body_class(body, self)
            for sc in config_s:
                break
            sc.modified = True

        else:
            sc = self.section_class(self)

        return sc

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

