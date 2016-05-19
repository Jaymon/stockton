import re

from captain import echo

from .. import cli
from .postfix import Postfix
from ..path import Filepath, Dirpath
from ..concur.formats.opendkim import OpenDKIM
from .base import Interface


class DomainKey(object):

    bits = 2048

    @property
    def keys_d(self):
        dk = DKIM()
        return dk.keys_d

    @property
    def txt_f(self):
        txt_f = Filepath(self.keys_d, "{}.txt".format(self.domain))
        return txt_f

    @property
    def private_f(self):
        private_f = Filepath(self.keys_d, "{}.private".format(self.domain))
        return private_f

    @property
    def text(self):
        dkim_text = "{} {} {}".format(self.v, self.k, self.p)
        return dkim_text

    @property
    def subdomain(self):
        m = re.match("^(\S+)", self.contents())
        return "{}.{}".format(m.group(1), self.domain)

    @property
    def v(self):
        mv = re.search("v=\S+", self.contents())
        return mv.group(0)

    @property
    def k(self):
        mk = re.search("k=\S+", self.contents())
        return mk.group(0)

    @property
    def p(self):
        contents = self.contents()
        mp = re.search("p=[^\"]+", contents)
        mps = re.findall("\"(?!\S=)(\S+?)\"", contents)
        return "".join([mp.group(0)] + mps)

    def __init__(self, domain):
        self.domain = domain

    def exists(self):
        return self.txt_f.exists()

    def contents(self):
        try:
            contents = self._contents
        except AttributeError:
            contents = self._contents = self.txt_f.contents()
        return contents

    def create(self):
        if self.exists(): return
        self.generate()

    def generate(self):
        bits = self.bits
        domain = self.domain
        keys_d = self.keys_d
        private_f = self.private_f
        #cli.run("opendkim-genkey --domain={} --verbose --directory=\"{}\"".format(
        cli.run("opendkim-genkey --bits={} --domain={} --directory=\"{}\"".format(
            bits,
            domain,
            keys_d.path
        ))

        private_f = Filepath(keys_d, "default.private")
        private_f.rename("{}.private".format(domain))
        private_f.chmod(600)
        private_f.chown("opendkim:opendkim")

        txt_f = Filepath(keys_d, "default.txt")
        txt_f.rename("{}.txt".format(domain)) # this makes self.txt_f and self.exists() work

    def __str__(self):
        return self.text


class DKIM(Interface):

    bits = 2048

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

    def config(self, path=OpenDKIM.dest_path):
        return OpenDKIM(prototype_path=path)

    def base_configs(self):
        return [self.config_f]

    def domainkey(self, domain):
        domk = DomainKey(domain)
        domk.bits = self.bits
        return domk

    def set_ip(self, ip_addr):
        """set the ip address into the hosts file"""
        if not ip_addr:
            raise ValueError("ip_addr is empty")

        hosts = [
            "127.0.0.1",
            "::1",
            "localhost",
            "192.168.0.1/24",
            ip_addr,
        ]

        trustedhosts_f = self.trustedhosts_f
        trustedhosts_f.writelines(hosts)

    def delete_domain(self, domain):
        # remove dkim settings
        self.signingtable_f.delete_lines(domain)
        self.trustedhosts_f.delete_lines(domain)

    def add_domains(self):
        p = Postfix()
        for domain in p.domains:
            self.add_domain(domain)

    def add_domain(self, domain, gen_key=False):
        keytable_f = self.keytable_f
        signingtable_f = self.signingtable_f
        trustedhosts_f = self.trustedhosts_f

        dk = self.domainkey(domain)
        private_f = dk.private_f

        if gen_key:
            dk.generate()
        else:
            dk.create()

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
        try:
            output = cli.run("/etc/init.d/opendkim status")
            if re.search("opendkim\s+is\s+running", output, flags=re.I):
                ret = True

        except RuntimeError:
            ret = False

        return ret

    def exists(self):
        return self.config_d.exists()

    def install(self):
        cli.package("opendkim", "opendkim-tools")
        self.config_d.create()
        self.keys_d.create()

    def uninstall(self):
        cli.purge("opendkim", "opendkim-tools")
        self.config_d.delete()
        for f in self.base_configs():
            f.delete()

