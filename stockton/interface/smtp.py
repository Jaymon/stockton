

from .. import cli
from ..path import Filepath
#from ..concur.formats.postfix import Main, SMTPd, Master


class SMTP(object):

    def add_user(self, username, password, domain):
        """adds an smtp user with credentials:

            user: username@domain
            pass: password

        username -- string -- the smtp username
        password -- string -- the smtp password
        domain -- string -- the domain the username belongs to
        """
        cli.run("echo \"{}\" | saslpasswd2 -c -u {} {} -p".format(password, domain, username))

        sasldb2 = Filepath("/etc/sasldb2")
        sasldb2.chmod(400)
        sasldb2.chown("postfix")

