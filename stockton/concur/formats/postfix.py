"""
Postfix specific configuration files, the file locations are for ubuntu 14.04
"""
import re

from . import generic
from . import base


class MainOption(base.ConfigOption):
    def _parse(self, fp):
        super(MainOption, self)._parse(fp)
        if self.is_valid():
            # let's make sure we don't have a multiline
            line_number = fp.line_number
            for c in fp:
                m = re.match("^\s+(\S+)", c.line)
                if m:
                    line = "\n" + fp.line
                    self.val += line
                    self.line += line
                    line_number += 1

                else:
                    #self.lines = re.split(",?\s*", self.val, re.M)
                    fp.rewind(line_number)
                    break


class Main(generic.EqualConfig):
    option_class = MainOption
    dest_path = "/etc/postfix/main.cf"
    # /usr/share/postfix/main.cf.dist has a rather complete example file


class SMTPd(generic.ColonConfig):
    dest_path = "/etc/postfix/sasl/smtpd.conf"


class MasterSection(base.ConfigSection):
    def _parse(self, fp):
        if not re.search("\s+-\s+", fp.line): return

        self.reset()
        commenters = self.config.commenters

        # service type  private unpriv  chroot  wakeup  maxproc command + args",
        m = re.match("^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", fp.line)
        if m:
            self.line = fp.line
            self.start_line_number = fp.line_number
            self.stop_line_number = self.start_line_number

            self.name = m.group(1).lstrip(commenters).lstrip()
            self.service_type = m.group(2)
            self.private = m.group(3)
            self.unpriv = m.group(4)
            self.chroot = m.group(5)
            self.wakeup = m.group(6)
            self.maxproc = m.group(7)
            self.cmd = m.group(8)

            for line_number, c in enumerate(fp):
                if isinstance(c, self.config.section_class):
                    self.stop_line_number = c.start_line_number - 1
                    fp.rewind(self.stop_line_number)
                    break

                elif isinstance(c, self.config.option_class):
                    self.options[c.name].append(line_number)
                    self.lines.append(c)

                elif isinstance(c, self.config.line_class):
                    self.lines.append(c)

    def __str__(self):
        if self.modified:
            s = "{}{}{}{}{}{}{}{}".format(
                self.name.ljust(max(10, len(self.name) + 1)),
                self.service_type.ljust(6),
                self.private.ljust(8),
                self.unpriv.ljust(8),
                self.chroot.ljust(8),
                self.wakeup.ljust(8),
                self.maxproc.ljust(8),
                self.cmd
            )

        else:
            s = self.line

        s2 = super(MasterSection, self).__str__()
        if s2:
            s += "\n" + s2
        return s


class MasterOption(base.ConfigOption):
    def _parse(self, fp):
        if "-o" in fp.line:
            self.name = fp.line

        commenters = self.config.commenters
        divider = self.config.option_divider
        m = re.match("^[{}]?\s*-o\s+(\S+)\s*{}\s*(.*)".format(commenters, divider), fp.line)
        if m:
            self.name = m.group(1)
            self.val = m.group(2)

    def format_set(self, name, divider, val):
        s = "  -o {}{}{}".format(name, divider, val)
        return s


class MasterLine(base.ConfigLine):
    def __str__(self):
        # TODO -- test this with an existing line to make sure it doesn't double indent
        return "  {}".format(self.line.lstrip())


class Master(base.Config):
    section_class = MasterSection
    option_class = MasterOption
    line_class = MasterLine
    dest_path = "/etc/postfix/master.cf"

