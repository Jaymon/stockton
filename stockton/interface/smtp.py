

from .. import cli
from ..path import Filepath
from ..concur.formats.postfix import SMTPd


class SMTP(object):
    @property
    def db_f(self):
        return Filepath("/etc/sasldb2")

    @property
    def config_f(self):
        return Filepath(SMTPd.dest_path)

    @property
    def config(self):
        config_f = self.config_f
        if config_f.exists():
            s = SMTPd(prototype_path=config_f.path)
        else:
            s = SMTPd()
        return s

    def add_user(self, username, password, domain):
        """adds an smtp user with credentials:

            user: username@domain
            pass: password

        username -- string -- the smtp username
        password -- string -- the smtp password
        domain -- string -- the domain the username belongs to
        """
        cli.run("echo \"{}\" | saslpasswd2 -c -u {} {} -p".format(password, domain, username))

        sasldb2 = self.db_f
        sasldb2.chmod(400)
        sasldb2.chown("postfix")

    def exists(self):
        return self.db_f.exists()

    def install(self):
        cli.package("sasl2-bin", "libsasl2-modules")

    def uninstall(self):
        cli.purge("sasl2-bin", "libsasl2-modules")
        self.config_f.delete()
        self.db_f.delete()

