import re

from captain import echo

from .. import cli
from ..path import Filepath, Dirpath
from ..concur.formats.postfix import Main, SMTPd, Master
from ..concur.formats.generic import SpaceConfig
from ..geo import IP


class Cert(object):

    @property
    def key(self):
        return Filepath(self.certs_d, "{}.key".format(self.domain))

    @property
    def crt(self):
        return Filepath(self.certs_d, "{}.crt".format(self.domain))

    @property
    def pem(self):
        return Filepath(self.certs_d, "{}.pem".format(self.domain))

    def __init__(self, domain):
        self.domain = domain
        self.certs_d = Dirpath("/etc/postfix/certs")
        self.bits = 4096

    def assure(self):
        if not self.exists():
            self.create()

    def exists(self):
        return self.pem.exists()

    def create(self):
        """write out a certificate for the domain"""
        self.certs_d.create()
        domain = self.domain

        certs_key = self.key
        certs_crt = self.crt
        certs_pem = self.pem

        ip = IP()
        country = ip.country
        state = ip.state
        city = ip.city

        cli.package("openssl", only_upgrade=True)

        # http://superuser.com/questions/226192/openssl-without-prompt
        cli.run(" ".join([
            "openssl req",
            "-new",
            "-newkey rsa:{}".format(self.bits),
            # openssl 1.0.2+ only, comment out above line and uncomment next 2
            #"-newkey ec",
            #"-pkeyopt ec_paramgen_curve:prime256v1",
            "-days 3650",
            "-nodes",
            "-x509",
            "-subj \"/C={}/ST={}/L={}/O={}/CN={}\"".format(
                country,
                state,
                city,
                domain,
                domain
            ),
            "-keyout {}".format(certs_key),
            "-out {}".format(certs_crt)
        ]))
        cli.run("cat {} {} > {}".format(certs_crt, certs_key, certs_pem))


class Postfix(object):

    @property
    def mailserver(self):
        m = self.main()
        return m["myhostname"].val

    @property
    def helo(self):
        return SpaceConfig(dest_path=self.helo_f.path)

    @property
    def helo_f(self):
        return Filepath("/etc/postfix/helo.regexp")

    @property
    def main_f(self):
        return Filepath(Main.dest_path)

    @property
    def main_live(self):
        """return the main config prototyped with the live main.cf"""
        return self.main()

    @property
    def main_new(self):
        """return the main config with no prototype, so brand spanking new"""
        return self.main("")

    @property
    def master_f(self):
        return Filepath(Master.dest_path)

    @property
    def config_d(self):
        return Dirpath("/etc/postfix")

    @property
    def virtual_d(self):
        return Dirpath(self.config_d, "virtual")

    @property
    def addresses_d(self):
        return Dirpath(self.virtual_d, "addresses")

    @property
    def domains_f(self):
        return Filepath(self.virtual_d, "domains")

    @property
    def domains(self):
        """return all the domains postfix has configured"""
        try:
            domains = set(self.domains_f.lines())
        except IOError:
            domains = set()
        return domains

    @property
    def addresses(self):
        for domain in self.domains:
            yield self.address(domain)

    def add_domain(self, domain, proxy_file, proxy_email):
        if not proxy_file:
            if not domain or not proxy_email:
                raise ValueError("Either pass in proxy_file or (domain and proxy_emails)")

        # create directory /etc/postfix/virtual
        virtual_d = self.virtual_d
        virtual_d.create()

        # create addresses directory
        addresses_d = self.addresses_d
        addresses_d.create()

        domains_f = self.domains_f
        domains_f.create()
        old_domains = self.domains
        new_domains = set()

        if proxy_file:
            echo.h3("Adding domain {} with addresses from {} to postfix", domain, proxy_file)
            f = Filepath(proxy_file)
            domain_f = Filepath(addresses_d, domain)
            f.copy(domain_f)
            new_domains.add(domain)

        elif proxy_email:
            echo.h3("Adding catchall for {} routing to {}", domain, proxy_email)
            domain_f = Filepath(addresses_d, domain)
            domain_c = SpaceConfig(dest_path=domain_f.path)
            domain_c["@{}".format(domain)] = proxy_email
            domain_c.save()
            new_domains.add(domain)

        domains_f.writelines(old_domains.union(new_domains))

        # this is an additive editing of the conf file, so we use the active conf
        # as the prototype
        m = self.main()
        m.update(
            ("virtual_alias_domains", domains_f.path),
            ("virtual_alias_maps", ",\n  ".join(("hash:{}".format(af) for af in self.addresses)))
        )
        m.save()

        for domain in new_domains:
            cli.run("postmap {}".format(self.address(domain)))

    def address(self, domain):
        addresses_f = Filepath(self.addresses_d, domain)
        return addresses_f

    def main(self, *path):
        """return the main config

        *path -- string -- pass in "" to not load any prototype, pass in a path
            to load that path as the prototype, pass in nothing to get the live
            main.cf file as the prototype

        return -- Main
        """
        if path:
            if path[0]:
                m = Main(prototype_path=path[0])

            else:
                m = Main()

        else:
            m = Main(prototype_path=Main.dest_path)

        return m

    def master(self, path=Master.dest_path):
        return Master(prototype_path=path)

    def main_backups(self):
        """return any backups of the Postfix main.cf file"""
        for mbak_f in self.config_d.files("main.*?\.bak$"):
            mbak = Main(dest_path=mbak_f.path, prototype_path=mbak_f.path)
            yield mbak

    def restart(self):
        try:
            cli.run("postfix status")

        except RuntimeError:
            cli.run("postfix start")

        finally:
            cli.run("postfix reload")

    def reset(self, **kwargs):
        delete_files = kwargs.get("really_delete_files", False)
        if not delete_files:
            raise ValueError("You want to delete files? pass in really_delete_files=True")

        # remove any .bak files in this directory, we do this to make sure any other
        # commands that configure postfix will be able to make correct snapshots of
        # the main.cf file to remain idempotent
        echo.h3("Clearing .bak files")
        postfix_d = Dirpath("/etc/postfix")
        postfix_d.delete_files(".bak$")

        virtual_d = self.virtual_d
        echo.h3("Clearing {}", virtual_d)
        virtual_d.clear()


    def is_running(self):
        ret = True
        try:
            cli.running("postfix")
        except RuntimeError:
            ret = False

        return ret

