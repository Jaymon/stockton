import re

from . import concur


class Main(concur.Config):
    dest_path = "/etc/postfix/main.cf"


class SMTPd(concur.Config):
    option_divider = ":"
    option_set_format = "{}{} {}"
    dest_path = "/etc/postfix/sasl/smtpd.conf"


class MasterSection(concur.ConfigSection):
    def _parse(self, fp):
        if not re.search("\s+-\s+", fp.line): return

        self.options = {}
        self.lines = []
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
                    self.options[c.name] = line_number
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


class MasterOption(concur.ConfigOption):
    def _parse(self, fp):
        if "-o" in fp.line:
            self.name = fp.line

        commenters = self.config.commenters
        divider = self.config.option_divider
        m = re.match("^[{}]?\s*-o\s+(\S+)\s*{}\s*(.*)".format(commenters, divider), fp.line)
        if m:
            self.name = m.group(1)
            self.val = m.group(2)

    def __str__(self):
        s = ""
        divider = self.config.option_divider
        if self.modified:
            s = "  -o {}{}{}".format(self.name, divider, self.val)

        else:
            s = super(MasterOption, self).__str__()

        return s


class Master(concur.Config):
    section_class = MasterSection
    option_class = MasterOption
    dest_path = "/etc/postfix/master.cf"

