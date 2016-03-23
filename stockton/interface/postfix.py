import re

from captain import echo

from .. import cli
from ..path import Filepath, Dirpath
from ..concur.formats.postfix import Main, SMTPd, Master
from ..concur.formats.generic import SpaceConfig

class Postfix(object):

    @property
    def mailserver(self):
        m = self.main()
        return m["myhostname"].val

    @property
    def main_f(self):
        return Filepath(Main.dest_path)

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


