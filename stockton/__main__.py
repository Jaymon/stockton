#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import argparse
import os
import subprocess
import re

from stockton import __version__
from stockton.postfixconfig import Main, SMTPd
from stockton.path import Dirpath, Filepath
import cli


class Command(object):
    def __init__(self, name):
        self.name = name

    def run_name(self, **kwargs):
        self.kwargs = kwargs
        name = self.name.replace("-", "_")
        method = getattr(self, name)
        return method()

    def assure_domain(self):
        self.assure_kwarg("domain", "Domain (eg, example.com)")

    def assure_mailserver(self):
        self.assure_kwarg("mailserver", "Mailserver for {0} (eg, mail.{0})".format(self.kwargs['domain']))

    def assure_kwarg(self, key, prompt):
        if key not in self.kwargs or not self.kwargs[key]:
            answer = cli.ask(prompt)
            self.kwargs[key] = answer

    def setup(self):
        return self.install()
        return self.configure_main()

    def install(self):
        cli.print_out("Installing Postfix")
        self.assure_domain()
        self.assure_mailserver()

        cli.run("apt-get update")
        cli.run("apt-get -y install --no-install-recommends postfix")
        cli.package("postfix")

    def configure_recv(self):
        cli.print_out("Configuring Postfix to receive emails")
        self.assure_domain()
        self.assure_mailserver()
        self.assure_kwarg("proxy_domains", "Need proxy_domains config directory")
        kwargs = self.kwargs

        # create directory /etc/postfix/virtual
        virtual_d = Dirpath("/etc/postfix/virtual")
        cli.print_out("Creating {}", virtual_d)
        virtual_d.create()

        # gather domains
        domains = set()
        cli.print_out("Compiling proxy domains...")
        addresses_f = Filepath(virtual_d, "addresses")
        with open(addresses_f.path, "w") as af:
            domains_d = Dirpath(kwargs["proxy_domains"])
            for f in domains_d.files():
                domain = f.name
                domain = re.sub("\.txt$", "", domain, flags=re.I)
                cli.print_out("Compiling proxy addresses from {}", domain)
                af.write(f.contents())
                af.write("\n\n")
                domains.add(domain)

            if kwargs["domain"] not in domains:
                self.assure_kwarg("final_destination", "Enter the final destination email address (eg, yourname@gmail.com)")
                af.write("@{} {}".format(kwargs["domain"], kwargs["final_destination"]))
                domains.add(kwargs["domain"])

        domains_f = Filepath(virtual_d, "domains")
        with open(domains_f.path, "w") as df:
            for domain in domains:
                df.write(domain)
                df.write("\n")

        m = Main()
        m.modify_all(
            ("myhostname", kwargs["mailserver"]),
            ("mydomain", kwargs["domain"]),
            ("myorigin", kwargs["domain"]),
            ("virtual_alias_domains", domains_f.path),
            ("virtual_alias_maps", "hash:{}".format(addresses_f.path))
        )
        m.save()

        cli.run("postmap {}".format(addresses_f))
        cli.postfix_reload()

    def configure_send(self):
        cli.print_out("Configuring Postfix to send emails")
        self.assure_domain()
        self.assure_mailserver()
        kwargs = self.kwargs

        cli.package("sasl2-bin", "libsasl2-modules")
        self.assure_kwarg("smtp_password", "Password for smtp access for {}".format(kwargs["domain"]))

        cli.run("echo \"{}\" | saslpasswd2 -c -u {} smtp -p".format(kwargs["smtp_password"], kwargs["domain"]))

        sasldb2 = Filepath("/etc/sasldb2")
        sasldb2.chmod(400)
        sasldb2.chown("postfix")

        s = SMTPd()
        s.modify_all(
            ("pwcheck_method", "auxprop"),
            ("auxprop_plugin", "sasldb"),
            ("mech_list", "PLAIN LOGIN CRAM-MD5 DIGEST-MD5 NTLM"),
            ("log_level", "7")
        )
        s.save()

        certs_d = Dirpath("/etc/postfix/certs")
        certs_d.create()
        certs_d.chown("postfix")
        certs_key = Filepath(certs_d, "{}.key".format(kwargs["domain"]))
        certs_crt = Filepath(certs_d, "{}.crt".format(kwargs["domain"]))
        certs_pem = Filepath(certs_d, "{}.pem".format(kwargs["domain"]))

        cli.run("apt-get -y install --only-upgrade openssl")

        cli.run(" ".join([
            "openssl req",
            "-new",
            "-newkey rsa:4096",
            # openssl 1.0.2+ only, comment out above line and uncomment next 2
            #"-newkey ec",
            #"-pkeyopt ec_paramgen_curve:prime256v1",
            "-days 3650",
            "-nodes",
            "-x509",
            # TODO -- make country, state and city set on cli
            "-subj \"/C=US/ST=CA/L=San Francisco/O={0}/CN={0}\"".format(kwargs["mailserver"]),
            "-keyout {}".format(certs_key),
            "-out {}".format(certs_crt)
        ]))
        cli.run("cat {} {} > {}".format(certs_crt, certs_key, certs_pem))
        certs_pem.chmod(400)
        certs_pem.chown("postfix")

        # make backup of master.cf
        master_f = Filepath("/etc/postfix/master.cf")
        suffix = ".bak"
        master_bak = Filepath("/etc/postfix/master.cf{}".format(suffix))
        if not master_bak.exists():
            master_f.backup(suffix)

        # add the config to master.cf to enable smtp sending

def main():
    '''
    cli hook

    return -- integer -- the exit code
    '''
    parser = argparse.ArgumentParser(description='Setup and manage an email proxy')
    names = ["setup", "configure-recv", "configure-send"]
    parser.add_argument('name', metavar='NAME', nargs='?', default="", help='the action to run', choices=names)
    parser.add_argument('--domain', dest='domain', default="", help='The email domain (eg, example.com)')
    parser.add_argument('--mailserver', dest='mailserver', default="", help='The domain mailserver (eg, mail.example.com)')
    parser.add_argument('--proxy-domains', dest='proxy_domains', default="", help='The directory containing virtual email mappings')
    parser.add_argument('--smtp-password', dest='smtp_password', default="", help='The smtp password')
#     parser.add_argument('--debug', dest='debug', action='store_true', help='print debugging info')
#     parser.add_argument("-v", "--version", action='version', version="%(prog)s {}".format(__version__))
#     parser.add_argument('--all', dest='run_all', action='store_true', help='run all tests if no NAME specified')

    # https://docs.python.org/2/library/unittest.html#command-line-options
#     parser.add_argument('--no-failfast', dest='not_failfast', action='store_false', help='turns off fail fast')
#     parser.add_argument('--no-buffer', dest='not_buffer', action='store_false', help='turns off buffer')


    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run command with sudo")

    args = parser.parse_args()

    c = Command(args.name)
    kwargs = vars(args)
    c.run_name(**kwargs)

    ret_code = 0

    return ret_code


sys.exit(main())

