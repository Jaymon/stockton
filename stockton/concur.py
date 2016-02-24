import re
import shlex



class ConfigLine(object):
    def __init__(self, line):
        line = line.rstrip()
        self.line = line

    def is_valid(self):
        return True

    def __str__(self):
        return self.line


class ConfigOption(ConfigLine):
    commenters = "#"
    divider = "="
    format_to_str = "{} {} {}" # key, divider, val

    def __init__(self, name=None, val=None, comment=None):
        self.name = name
        self.val = val
        self.comment = comment
        self.modified = True

    def is_valid(self):
        return bool(self.name)

    def parse(self, line):
        line = line.rstrip()
        name = ""
        val = ""
        comment = ""

        if re.match("^[^{}]\S+".format(self.commenters), line): # name = val
            name, val = re.split("\s*{}\s*".format(self.divider), line, 2)

        elif re.match("^[{}]\s*\S+\s*{}".format(self.commenters, self.divider), line): # # name = val
            l = re.sub("^[{}]\s*".format(self.commenters), "", line)
            name, val = re.split("\s*{}\s*".format(self.divider), l, 2)

        bits = re.split("\s[{}]\s*".format(self.commenters), val, 2)
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
            s = self.format_to_str.format(self.name, self.divider, self.val)
            if self.comment:
                s += " {} {}".format(self.commenters[0], self.comment)

        else:
            s = super(ConfigOption, self).__str__()

        return s


class ConfigSection(ConfigOption):
    def __init__(self, name=None):
        super(ConfigSection, self).__init__(name)
        self.lines = []
        self.options = {}

    def parse(self, line):
        return


#     def append()




# Config will create a Section instance and pass it the file handler, that will parse
# the file handle until it finishes or finds another section, then it will return the current line,
# the file pointer, and the line number


the Config is more a ConfigFile object, it is the master class

The section is the one that will need to know about commenters, and it will decide
when to create option and line classes

the option class will only need to know dividers and the format, maybe commenters
if we want to be able to catch the commented out options?

the section parser will take a file pointer, the option parser will take a line, we might
want it to take a fp also so it can handle multiline options


class Config(object):
    """config parser that allows you to modify the parsed file and write it back out

    we don't use shlex because it didn't preserve comments
    https://docs.python.org/2/library/shlex.html 

    If an ini specific parser is added at a later date, use this?
    https://docs.python.org/2/library/configparser.html
    """

    commenters = "#"

    option_divider = "="

    option_set_format = "{} {} {}" # key, divider, val

    line_class = ConfigLine

    option_class = ConfigOption

    section_class = ConfigSection


    dest_path = ""

    prototype_path = ""

    @property
    def prototype_path(self):
        return self._prototype_path

    @prototype_path.setter
    def prototype_path(self, val):
        self._prototype_path = val
        self.parse_prototype(val)

    def __init__(self, dest_path="", prototype_path=""):
        if prototype_path:
            self.prototype_path = prototype_path

        if dest_path:
            self.dest_path = dest_path

        self.name_map = {}
        self.lines = []

    def update_instance(self, instance):
        instance.commenters = self.commenters
        instance.option_divider = self.option_divider
        instance.option_set_format = self.option_set_format
        instance.line_class = self.line_class
        instance.option_class = self.option_class
        instance.section_class = self.section_class

    def create_section(self, *args, **kwargs):
        instance = self.section_class(*args, **kwargs)
        self.update_instance(instance)
        return instance

    def parse_prototype(self, path):
        self.sections = {}
        self.options = {}
        self.lines = []

        with open(path, "r") as f:
            current_section = None
            for line_number, line in enumerate(f):

                cs = self.section_class()
                cs.parse(line)
                if cs.is_valid():
                    current_section = cs
                    self.lines.append(cs)
                    self.sections[cs.name] = line_number

                else:
                    co = self.option_class()
                    co.parse(line)
                    if co.is_valid():
                        if current_section:
                            current_section.append(co, line_number)

                        else:
                            self.lines.append(co)
                            self.options[co.name] = line_number

                    else:
                        cl = self.line_class(line)
                        self.lines.append(cl)

    def modify(self, name, val):
        if name in self.name_map:
            cl = self.lines[self.name_map[name]]
            cl.val = val
            cl.modified = True

        else:
            cl = self.option_class(name, val)
            self.name_map[name] = len(self.lines)
            self.lines.append(cl)

    def modify_all(self, *args, **kwargs):
        for k, v in args:
            self.modify(k, v)

        for k, v in kwargs.items():
            self.modify(k, v)

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

# c = Config(prototype_path="main-example.cf")
# pout.v(str(c))
# 
# pout.b()
# 
# c.modify("myhostname", "some.random.mailserver.com")
# c.modify("smtpd_tls_cert_file", "/path/to/some/pem.pem")
# 
# pout.v(str(c))








# with open("main-example.cf") as f:
#     for line in f:
#         token = shlex.split(line, comments=True, posix=True)
#         pout.v(token)

#     sh = shlex.shlex(f, posix=True)
#     for token in sh.get_token():
#         pout.v(token)

