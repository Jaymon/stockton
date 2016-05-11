import re

from captain import echo

from .. import cli
from .postfix import Postfix
from ..path import Filepath, Dirpath
from ..concur.formats.opendkim import OpenDKIM
from .base import Interface


class DomainKey(object):
    @property
    def txt_f(self):
        dk = DKIM()
        txt_f = Filepath(dk.keys_d, "{}.txt".format(self.domain))
        return txt_f

    @property
    def text(self):
        dkim_text = "{} {} {}".format(self.v, self.k, self.p)
        return dkim_text

    def __init__(self, domain):
        self.domain = domain

        contents = self.txt_f.contents()
        m = re.match("^(\S+)", contents)
        self.subdomain = "{}.{}".format(m.group(1), domain)

        mv = re.search("v=\S+", contents)
        mk = re.search("k=\S+", contents)
        mp = re.search("p=[^\"]+", contents)
        mps = re.findall("\"(?!\S=)(\S+?)\"", contents)
        self.v = mv.group(0)
        self.k = mk.group(0)
        self.p = "".join([mp.group(0)] + mps)

    def __str__(self):
        return self.text


class DKIM(Interface):

    @property
    def config(self):
        return OpenDKIM(prototype_path=self.config_f.path)

    @property
    def config_f(self):
        return Filepath(OpenDKIM.dest_path)

    @property
    def config_d(self):
        return Dirpath("/etc/opendkim")

    @property
    def keys_d(self):
        return Dirpath(self.config_d, "keys")

    @property
    def keytable_f(self):
        return Filepath(self.config_d, "KeyTable")

    @property
    def signingtable_f(self):
        return Filepath(self.config_d, "SigningTable")

    @property
    def trustedhosts_f(self):
        return Filepath(self.config_d, "TrustedHosts")

    def __init__(self):
        self.bits = 2048

    def base_configs(self):
        return [self.config_f]

    def domainkey(self, domain):
        return DomainKey(domain)

    def add_domains(self):
        p = Postfix()
        for domain in p.domains:
            self.add_domain(domain)

    def add_domain(self, domain, gen_key=False):
        keys_d = self.keys_d
        keytable_f = self.keytable_f
        signingtable_f = self.signingtable_f
        trustedhosts_f = self.trustedhosts_f

        private_f = Filepath(keys_d, "{}.private".format(domain))
        txt_f = Filepath(keys_d, "{}.txt".format(domain))
        if not txt_f.exists() or gen_key:
            #cli.run("opendkim-genkey --domain={} --verbose --directory=\"{}\"".format(
            cli.run("opendkim-genkey --bits={} --domain={} --directory=\"{}\"".format(
                self.bits,
                domain,
                keys_d.path
            ))

            private_f = Filepath(keys_d, "default.private")
            private_f.rename("{}.private".format(domain))
            private_f.chmod(600)
            private_f.chown("opendkim:opendkim")

            txt_f = Filepath(keys_d, "default.txt")
            txt_f.rename("{}.txt".format(domain))

            dk = self.domainkey(domain)

        if not keytable_f.contains(domain):
            keytable_f.append("{} {}:default:{}\n".format(
                dk.subdomain,
                domain,
                private_f.path
            ))

        if not signingtable_f.contains(domain):
            signingtable_f.append("{} {}\n".format(
                domain,
                dk.subdomain
            ))

        if not trustedhosts_f.contains(domain):
            trustedhosts_f.append("*.{}\n".format(domain))

    def start(self):
        cli.run("/etc/init.d/opendkim start")

    def restart(self):
        if self.is_running():
            cli.run("/etc/init.d/opendkim restart")
        else:
            self.start()

    def stop(self):
        cli.run("/etc/init.d/opendkim stop")

    def is_running(self):
        ret = False
        output = cli.run("/etc/init.d/opendkim status")
        if re.search("opendkim\s+is\s+running", output, flags=re.I):
            ret = True
        return ret

    def install(self):
        cli.package("opendkim", "opendkim-tools")
        self.config_d.create()
        self.keys_d.create()

    def uninstall(self):
        cli.purge("opendkim", "opendkim-tools")
        self.config_d.delete()
        for f in self.base_configs():
            f.delete()

