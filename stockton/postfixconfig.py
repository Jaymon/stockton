import re

from . import concur


class Main(concur.Config):
    dest_path = "/etc/postfix/main.cf"
#     def __init__(self):
#         super(Main, self).__init__(dest_path="/etc/postfix/main.cf")




class SMTPdOption(concur.ConfigOption):
    divider = ":"
    format_to_str = "{}{} {}"


class SMTPd(concur.Config):
    option_class = SMTPdOption
    dest_path = "/etc/postfix/sasl/smtpd.conf"
#     def __init__(self):
#         super(SMTPd, self).__init__(dest_path="/etc/postfix/sasl/smtpd.conf")


class MasterSection(concur.ConfigSection):
    def parse(self, fp):
        if not re.search("\s+-\s+", fp.line): return

        self.options = {}
        self.lines = []

        # service type  private unpriv  chroot  wakeup  maxproc command + args",
        m = re.match("^[^{}]?\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)".format(self.commenters), fp.line)
        if m:
            self.service_line = fp.line
            self.name = m.group(1)
            self.service_type = m.group(2)
            self.private = m.group(3)
            self.unpriv = m.group(4)
            self.chroot = m.group(5)
            self.wakeup = m.group(6)
            self.maxproc = m.group(7)
            self.cmd = m.group(8)

            for line_number, c in enumerate(fp):
                if isinstance(c, fp.config.section_class):
                    break

                elif isinstance(c, fp.config.option_class):
                    self.options[c.name] = line_number
                    self.lines.append(c)

                elif isinstance(c, fp.config.line_class):
                    self.lines.append(c)

    def __str__(self):
        s = self.service_line + "\n"
        s += super(MasterSection, self).__str__()
        return s


class MasterOption(concur.ConfigOption):
    def parse(self, fp):
        if "-o" in fp.line:
            self.name = fp.line

        m = re.match("^[^{}]?\s*-o\s+(\S+)\s*{}\s*(.*)".format(self.commenters, self.divider), fp.line)
        if m:
            self.name = m.group(1)
            self.val = m.group(2)

        self.line = fp.line
        self.modified = False


class Master(concur.Config):
    section_class = MasterSection
    option_class = MasterOption
    dest_path = "/etc/postfix/master.cf"





# c = Master(prototype_path="/etc/postfix/master.cf.bak")
# pout.v(str(c))

pout.b()
