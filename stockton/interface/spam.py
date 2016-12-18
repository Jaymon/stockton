import re

from captain import echo

from .. import cli
from .postfix import Postfix
from ..path import Dirpath, Filepath, Sentinal
#from ..concur.formats.opendkim import OpenDKIM
from ..concur.formats.spamassassin import SpamAssassin, Local
from ..concur.formats.generic import EqualConfig


class Spam(object):
    """Installs and adds configuration hooks for SpamAssassin

    https://spamassassin.apache.org/full/3.4.x/doc/
    http://wiki.apache.org/spamassassin/ImproveAccuracy
    https://aikar.co/2014/09/05/filtering-spam-forwarding-email-postfixspamassassin/
    https://github.com/apache/spamassassin
    """

    perl_packages = [
        "libgeo-ip-perl",
        "libdigest-sha-perl",
        "libdbi-perl",
        "libio-socket-ip-perl",
        "libencode-detect-perl",
        "libnet-patricia-perl",
        "libmail-dkim-perl",
        "libmail-spf-perl",
    ]

    @property
    def user(self):
        return "debian-spamd"

    @property
    def home_d(self):
        # http://askubuntu.com/questions/410244/a-command-to-list-all-users-and-how-to-add-delete-modify-users
        username = self.user
        path = cli.run(
            'grep "{}" /etc/passwd | cut -f6 -d":"'.format(username),
            capture_output=True
        ).strip()

        if not path:
            raise ValueError("could not find home directory for user {}".format(username))

        return Dirpath(path)

    @property
    def config_f(self):
        return Filepath(SpamAssassin.dest_path)

    @property
    def local_f(self):
        return Filepath(Local.dest_path)

    def base_configs(self):
        return [self.config_f, self.local_f]

    def pre_config(self, basename):
        """return configuration for one of the pre configuration files of spam assassin

        :param basename: something like v310
        :returns: the configuration instance
        """
        if not basename.endswith(".pre"):
            basename = "{}.pre".format(basename)
        f = Filepath(Filepath(Local.dest_path).directory, basename)
        return Local(prototype_path=str(f), dest_path=str(f))

    def config(self, path=SpamAssassin.dest_path):
        return SpamAssassin(prototype_path=path)

    def local(self, path=Local.dest_path):
        return Local(prototype_path=path)

    def start(self):
        try:
            o = cli.run("/etc/init.d/spamassassin start")
        except RuntimeError as e:
            if not re.search("already\s+running", str(e), re.I):
                raise

    def restart(self):
        if self.is_running():
            cli.run("/etc/init.d/spamassassin restart")
        else:
            self.start()

    def stop(self):
        cli.run("/etc/init.d/spamassassin stop")

    def is_running(self):
        ret = True
        try:
            cli.run("/etc/init.d/spamassassin status")
        except RuntimeError:
            ret = False
        return ret

    def exists(self):
        ret = True
        try:
            #self.stop()
            cli.run("/etc/init.d/spamassassin status")
        except cli.RunError as e:
            ret = not e.is_missing()
        return ret

    def lint(self):
        """Return the output from checking SA's configuration"""
        return cli.run("spamassassin -D --lint")

    def install(self):
        # make sure the packages are installed
        cli.package("spamassassin", "spamc")

        # these help make SA work better
        cli.package("libgeoip-dev", "libssl-dev") # we don't remove these in uninstall()
        cli.package(*self.perl_packages)

        # add the spam user
        # update 4-16-2016 let's just use debian-spamd and /var/lib/spamassassin
        #cli.run("adduser --disabled-login --disabled-password --gecos "" spamd")
        if not self.home_d.exists():
            raise ValueError("Home directory {} does not exist".format(self.home_d))

    def uninstall(self):
        try:
            self.stop()
        except cli.RunError as e:
            if not e.is_missing():
                raise

        cli.purge("spamassassin", "spamc")
        cli.purge(*self.perl_packages)


class Razor(object):
    """Installs razor

    http://razor.sourceforge.net/
    https://digitalenvelopes.email/blog/debian-integrate-razor-spamassassin/
    https://wiki.apache.org/spamassassin/RazorSiteWide
    https://spamassassin.apache.org/full/3.4.x/doc/Mail_SpamAssassin_Plugin_Razor2.html
    https://wiki.apache.org/spamassassin/UsingRazor

    https://wiki.apache.org/spamassassin/RazorHowToTell
    to test --
        razor-check -d < /usr/share/doc/spamassassin/examples/sample-spam.txt
        spamassassin -D razor2 2>&1 < /usr/share/doc/spamassassin/examples/sample-spam.txt

        This is the one I've been using recently to make sure everything is working:
        echo "test" | spamassassin -t -D razor2
    """
    @property
    def home_d(self):
        return Dirpath("/etc/razor")

    @property
    def config_f(self):
        return Filepath(self.home_d, "razor-agent.conf")

    def test(self):
        r = cli.run("spamassassin -D razor2 < /usr/share/doc/spamassassin/examples/sample-spam.txt")
        return r

    def config(self, path=""):
        if not path:
            path = self.config_f
        path = str(path)
        dest_path = str(self.config_f)
        return EqualConfig(dest_path=dest_path, prototype_path=path)

    def start(self):
        pass

    def restart(self):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False

    def exists(self):
        ret = True
        try:
            cli.run("which razor-admin")
        except cli.RunError as e:
            ret = False
        return ret

    def install(self):
        # make sure the packages are installed
        cli.package("razor")

        cli.run("razor-admin -d -home=\"{}\" -create".format(self.home_d))
        cli.run("razor-admin -d -home=\"{}\" -register".format(self.home_d))
        # razor-admin -d -home=/etc/razor -create
        # razor-admin -d -home=/etc/razor -register

    def uninstall(self):
        cli.purge("razor")


class Pyzor(object):
    """Installs pyzor

    https://digitalenvelopes.email/blog/debian-integrate-pyzor-spamassassin/
    https://wiki.apache.org/spamassassin/UsingPyzor

    to test:
        echo "test" | spamassassin -D pyzor
        spamassassin -D pyzor < /usr/share/doc/spamassassin/examples/sample-spam.txt
    """
    def test(self):
        r = cli.run("spamassassin -D pyzor < /usr/share/doc/spamassassin/examples/sample-spam.txt")
        return r

    def start(self):
        pass

    def restart(self):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False

    def ping(self):
        output = cli.run("pyzor ping")
        return "200" in output

    def exists(self):
        ret = True
        try:
            cli.run("which pyzor")
        except cli.RunError as e:
            ret = False
        return ret

    def install(self):
        cli.package("pyzor")

        cli.run("pyzor discover")

        if not self.ping():
            raise IOError("Pyzor ping was unsuccessful")

    def uninstall(self):
        cli.purge("pyzor")


class DCC(object):
    """Install DCC

    http://forum.directadmin.com/showthread.php?t=53179&s=5d1d3471d0ca0a99b019f457758f86c4&p=272841#post272841
    https://www.dcc-servers.net/dcc/FAQ.html
    https://wiki.apache.org/spamassassin/InstallingDCC

    to test:
        spamassassin -D DCC < /usr/share/doc/spamassassin/examples/sample-spam.txt
    """
    @property
    def user(self):
        return "mail"

    @property
    def home_d(self):
        return Dirpath("/var/lib/dcc")

    def test(self):
        r = cli.run("spamassassin -D DCC < /usr/share/doc/spamassassin/examples/sample-spam.txt")
        return r

    def start(self):
        pass

    def restart(self):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False

    def exists(self):
        ret = True
        try:
            cli.run("which cdcc")
        except cli.RunError as e:
            ret = False
        return ret

    def install(self):
        tmpdir = Dirpath.get_temp()
        tar_name = "dcc-dccproc.tar.Z"
        tar_src = "http://www.dcc-servers.net/dcc/source/dcc-dccproc.tar.Z"

        tar_f = Filepath(tmpdir, tar_name)
        if not tar_f.exists():
            cli.run("wget -O {} {}".format(tar_name, tar_src), cwd=tmpdir.path)

        # Build and install.
        cli.run("tar xzvf {}".format(tar_name), cwd=tmpdir.path)
        build_d = tmpdir.descendant(r"dcc-dccproc-")
        run_d = self.home_d

        cli.run(
            "".join([
                "./configure "
                "--bindir=$(PREFIX)/bin ",
                "--libexecdir=$(PREFIX)/lib/dcc ",
                "--mandir=$(PREFIX)/man ",
                "--homedir={} ".format(run_d),
                "--with-uid={} ".format(self.user),
                "--with-gid={}".format(self.user)
            ]),
            cwd=build_d.path
        )
        cli.run("make", cwd=build_d.path)
        cli.run("make install", cwd=build_d.path)
        run_d.chown(self.user, R=True)
        run_d.chgrp(self.user, R=True)

    def uninstall(self):
        #cli.purge("razor")
        for path in ["/lib/dcc", "/var/lib/dcc"]:
            d = Dirpath(path)
            d.delete()

        # clean up executable files
        d = Dirpath("/bin")
        d.delete_files(r"^c?dcc")

        # delete man
        d = Dirpath("/man/man8")
        d.delete_files(r"^c?dcc")

