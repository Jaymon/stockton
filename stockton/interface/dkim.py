import re

from captain import echo

from .. import cli
from .postfix import Postfix
from ..path import Filepath, Dirpath
from ..concur.formats.opendkim import OpenDKIM


class DKIM(object):

    @property
    def config_f(self):
        return Filepath(OpenDKIM.dest_path)

    @property
    def opendkim_d(self):
        return Dirpath("/etc/opendkim")

    @property
    def keys_d(self):
        return Dirpath(self.opendkim_d, "keys")

    @property
    def keytable_f(self):
        return Filepath(self.opendkim_d, "KeyTable")

    @property
    def signingtable_f(self):
        return Filepath(self.opendkim_d, "SigningTable")

    @property
    def trustedhosts_f(self):
        return Filepath(self.opendkim_d, "TrustedHosts")

    def add_domains(self):
        #     opendkim_d = Dirpath("/etc/opendkim")
        #     keys_d = Dirpath(opendkim_d, "keys")
        #     keytable_f = Filepath(opendkim_d, "KeyTable")
        #     keytable_f.clear()
        #     signingtable_f = Filepath(opendkim_d, "SigningTable")
        #     signingtable_f.clear()
        #     trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
        #     trustedhosts_f.clear()

        p = Postfix()
        for domain in p.domains:
            self.add_domain(domain)

    def add_domain(self, domain, gen_key=False):
        echo.h3("Configuring DKIM for {}", domain)

        opendkim_d = self.opendkim_d
        keys_d = self.keys_d
        keytable_f = self.keytable_f
        signingtable_f = self.signingtable_f
        trustedhosts_f = self.trustedhosts_f

        private_f = Filepath(keys_d, "{}.private".format(domain))
        txt_f = Filepath(keys_d, "{}.txt".format(domain))
        if not txt_f.exists() or gen_key:
            #cli.run("opendkim-genkey --domain={} --verbose --directory=\"{}\"".format(
            cli.run("opendkim-genkey --bits=2048 --domain={} --directory=\"{}\"".format(
                domain,
                keys_d.path
            ))

            private_f = Filepath(keys_d, "default.private")
            private_f.rename("{}.private".format(domain))
            private_f.chmod(600)
            private_f.chown("opendkim:opendkim")

            txt_f = Filepath(keys_d, "default.txt")
            txt_f.rename("{}.txt".format(domain))

        if not keytable_f.contains(domain):
            keytable_f.append("default._domainkey.{} {}:default:{}\n".format(
                domain,
                domain,
                private_f.path
            ))

        if not signingtable_f.contains(domain):
            signingtable_f.append("{} default._domainkey.{}\n".format(
                domain,
                domain
            ))

        if not trustedhosts_f.contains(domain):
            trustedhosts_f.append("*.{}\n".format(domain))


    def restart(self):
        output = cli.run("/etc/init.d/opendkim status", capture_output=True)
        if re.search("opendkim\s+is\s+running", output, flags=re.I):
            cli.run("/etc/init.d/opendkim start")

        else:
            cli.run("/etc/init.d/opendkim restart")


