
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


class MasterOption(concur.ConfigOption):
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



class Master(concur.Config):
    option_class = MasterOption
    dest_path = "/etc/postfix/master.cf"





# c = Master(prototype_path="/etc/postfix/master.cf.bak")
# pout.v(str(c))

pout.b()
