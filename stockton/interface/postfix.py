import re
import time

from captain import echo

from .. import cli
from ..path import Filepath, Dirpath
from ..concur.formats.postfix import Main, SMTPd, Master
from ..concur.formats.generic import SpaceConfig
from ..geo import IP
from .base import Interface


class Cert(object):

    @property
    def key_f(self):
        return Filepath(self.certs_d, "{}.key".format(self.domain))

    @property
    def crt_f(self):
        return Filepath(self.certs_d, "{}.crt".format(self.domain))

    @property
    def pem_f(self):
        return Filepath(self.certs_d, "{}.pem".format(self.domain))

    def __init__(self, domain):
        self.domain = domain
        self.certs_d = Dirpath("/etc/postfix/certs")
        self.bits = 4096

    def assure(self):
        if not self.exists():
            self.create()

    def exists(self):
        return self.pem_f.exists()

    def create(self):
        """write out a certificate for the domain"""
        self.certs_d.create()
        domain = self.domain

        certs_key = self.key_f
        certs_crt = self.crt_f
        certs_pem = self.pem_f

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


class Postfix(Interface):
    @property
    def mailserver(self):
        m = self.main()
        return m["myhostname"].val

    @property
    def helo(self):
        return SpaceConfig(dest_path=self.helo_f.path)

    @property
    def helo_f(self):
        return Filepath(self.config_d, "helo.regexp")

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

    def cert(self, domain):
        return Cert(domain)

    def base_configs(self):
        return [self.main_f, self.master_f]

    def autodiscover_domain(self, proxy_f):
        """given a proxy file, discover the domain it represents by looking through
        each line and making sure the first email addresses all match"""
        if not proxy_f:
            raise ValueError("proxy_f does not contain a valid path")

        proxy_f = Filepath(proxy_f)
        domain_check = set()
        for line in proxy_f:
            m = re.match("^(\S*@\S+)", line)
            if m:
                bits = m.group(1).split("@", 1)
                if len(bits) == 2:
                    domain_check.add(bits[1])

        if len(domain_check) == 1:
            domain = domain_check.pop()

        else:
            raise ValueError("Found multiple domains in proxy_file {}".format(proxy_f))

        return domain

    def delete_domain(self, domain):
        # remove postfix settings
        virtual_d = self.virtual_d

        domains_f = self.domains_f
        domains_f.delete_lines("^{}$".format(domain))

        addresses_d = self.addresses_d
        addresses_d.delete_files("^{}".format(domain))

        domain_hashes = []
        for d in domains_f.lines():
            domain_f = Filepath(addresses_d, d)
            domain_hashes.append("hash:{}".format(domain_f.path))

        m = self.main()
        m["virtual_alias_maps"] = ",\n  ".join(domain_hashes)
        m.save()

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
            domain_f = self.address(domain)
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

    def main(self, path=Main.dest_path):
        return Main(prototype_path=path)

#     def main(self, *path):
#         """return the main config
# 
#         *path -- string -- pass in "" to not load any prototype, pass in a path
#             to load that path as the prototype, pass in nothing to get the live
#             main.cf file as the prototype
# 
#         return -- Main
#         """
#         if path:
#             if path[0]:
#                 m = Main(prototype_path=path[0])
# 
#             else:
#                 m = Main()
# 
#         else:
#             m = Main(prototype_path=Main.dest_path)
# 
#         return m

    def master(self, path=Master.dest_path):
        path = str(path)
        return Master(prototype_path=path)

    def main_backups(self):
        """return any backups of the Postfix main.cf file"""
        for mbak_f in self.config_d.files("main.*?\.bak$"):
            mbak = Main(dest_path=mbak_f.path, prototype_path=mbak_f.path)
            yield mbak

    def _run(self, cmd):
        """this wraps the normal command in a command that will make sure it works"""
        #return cli.run('script -c "{}" -q STDOUT --return'.format(cmd))
        return cli.run('script -c "{}" -q --return'.format(cmd))

    def start(self):
        try:
            self._run("postfix start")
        except RuntimeError as e:
            if not re.search("Postfix\s+mail\s+system\s+is\s+already\s+running", str(e), re.I):
                raise

    def restart(self):
        if self.is_running():
            self._run("postfix reload")
        else:
            self.start()

    def stop(self):
        o = self._run("postfix stop")
#         for x in range(20):
#             if self.is_running():
#                 time.sleep(0.1)
#             else:
#                 break

    def is_running(self):
        try:
            self._run("postfix status")
            ret = True

        except RuntimeError:
            ret = False

        return ret

    def exists(self):
        return self.config_d.exists()

    def install(self):
        cli.package("postfix")

    def uninstall(self):
        try:
            self.stop()
        except cli.RunError as e:
            if not e.is_missing():
                raise

        cli.purge("postfix")
        self.config_d.delete()

