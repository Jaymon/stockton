#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import argparse
import os
import subprocess
import re

from stockton import __version__
from stockton.concur.formats.postfix import Main, SMTPd, Master
from stockton.concur.formats.opendkim import OpenDKIM
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
        # TODO -- if postfix is already installed then bak files need to be cleared, etc
        # the key is re-running should be idempotent

        self.install()
        self.configure_recv()
        self.configure_send()
        self.configure_dkim()
        self.configure_srs()
        #self.lockdown()

    def install(self):
        cli.print_out("Installing Postfix")
        self.assure_domain()
        self.assure_mailserver()

        cli.run("apt-get update")
        #cli.run("apt-get -y install --no-install-recommends postfix")

        # http://serverfault.com/questions/143968/automate-the-installation-of-postfix-on-ubuntu
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        #cli.run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No configuration'\"")

        cli.package("postfix")

    def configure_recv(self):
        # http://www.postfix.org/VIRTUAL_README.html

        cli.print_out("Configuring Postfix to receive emails")
        self.assure_domain()
        self.assure_mailserver()
        #self.assure_kwarg("proxy_domains", "Need proxy_domains config directory")
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
            p = kwargs.get("proxy_domains", "")
            if p:
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
                af.write("@{} {}\n".format(kwargs["domain"], kwargs["final_destination"]))
                domains.add(kwargs["domain"])

        domains_f = Filepath(virtual_d, "domains")
        with open(domains_f.path, "w") as df:
            for domain in domains:
                df.write(domain)
                df.write("\n")

        m = Main()
        m.update(
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


        # https://help.ubuntu.com/lts/serverguide/postfix.html#postfix-sasl
        # http://www.postfix.org/SASL_README.html

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
        s.update(
            ("pwcheck_method", "auxprop"),
            ("auxprop_plugin", "sasldb"),
            ("mech_list", "PLAIN LOGIN CRAM-MD5 DIGEST-MD5 NTLM"),
            ("log_level", "7")
        )
        s.save()

        certs_d = Dirpath("/etc/postfix/certs")
        certs_d.create()
        #certs_d.chown("postfix")
        certs_key = Filepath(certs_d, "{}.key".format(kwargs["domain"]))
        certs_crt = Filepath(certs_d, "{}.crt".format(kwargs["domain"]))
        certs_pem = Filepath(certs_d, "{}.pem".format(kwargs["domain"]))

        #cli.run("apt-get -y install --only-upgrade openssl")
        cli.package("openssl", only_upgrade=True)

        # http://superuser.com/questions/226192/openssl-without-prompt
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
        #certs_pem.chmod(400)
        #certs_pem.chown("postfix")

        # make backup of master.cf
        master_f = Filepath(Master.dest_path)
        master_bak = master_f.backup(ignore_existing=False)

        # add the config to master.cf to enable smtp sending
        m = Master(prototype_path=master_bak.path)
        m["submission"].modified = True
        m["submission"].update(
            ("syslog_name", "postfix/submission"),
            ("smtpd_tls_security_level", "may"),
            ("smtpd_tls_cert_file", certs_pem.path),
            ("smtpd_sasl_auth_enable", "yes"),
            ("smtpd_reject_unlisted_recipient", "no"),
            ("smtpd_relay_restrictions", "permit_sasl_authenticated,reject"),
            ("milter_macro_daemon_name", "ORIGINATING")
        )
        m.save()

        cli.postfix_reload()

    def configure_dkim(self):

        # setup for multi-domain support thanks to
        # http://askubuntu.com/questions/438756/using-dkim-in-my-server-for-multiple-domains-websites
        # http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
        # http://edoceo.com/howto/opendkim
        # https://help.ubuntu.com/community/Postfix/DKIM


        cli.print_out("Configuring Postfix to use DKIM")
        #self.assure_domain()
        #self.assure_mailserver()
        kwargs = self.kwargs

        cli.package("opendkim", "opendkim-tools")

        opendkim_d = Dirpath("/etc/opendkim")
        opendkim_d.create()

        keys_d = Dirpath(opendkim_d, "keys")
        keys_d.create()

        hosts = [
            "127.0.0.1",
            "::1",
            "localhost",
            "192.168.0.1/24",
        ]
        # could also use https://pypi.python.org/pypi/netifaces but this seemed easier
        # http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
        external_ip = cli.ip()
        m = re.match("(?:\d+\.){4}", external_ip)
        if m:
            hosts.append(m.group(1))
        hosts.append("")
        trustedhosts_f = opendkim_d.create_file("TrustedHosts", "\n".join(hosts))

        keytable_f = opendkim_d.create_file("KeyTable")
        signingtable_f = opendkim_d.create_file("SigningTable")

        # make backup of config
        config_f = Filepath(OpenDKIM.dest_path)
        config_bak = config_f.backup(ignore_existing=False)

        c = OpenDKIM(prototype_path=config_bak.path)
        c.update(
            ("Canonicalization", "relaxed/simple"),
            ("Mode", "sv"),
            ("SubDomains", "yes"),
            ("Syslog", "yes"),
            ("LogWhy", "yes"),
            ("UMask", "022"),
            ("UserID", "opendkim:opendkim"),
            ("KeyTable", keytable_f.path),
            ("SigningTable", signingtable_f.path),
            ("ExternalIgnoreList", trustedhosts_f.path),
            ("InternalHosts", trustedhosts_f.path),
            ("Socket", "inet:8891@localhost")
        )
        c.save()

        m = Main(prototype_path=Main.dest_path)
        m.update(
            ("milter_default_action", "accept"),
            # http://lists.opendkim.org/archive/opendkim/users/2011/08/1297.html
            ("milter_protocol", "6"),
            ("smtpd_milters", "inet:localhost:8891"),
            ("non_smtpd_milters", "inet:localhost:8891"),
        )
        m.save()

        domains_f = Filepath("/etc/postfix/virtual/domains")
        for domain in domains_f.lines():
            self.add_dkim_domain(domain.strip())

        cli.postfix_reload()
        cli.opendkim_reload()

    def add_dkim_domain(self, domain):
        cli.print_out("Configuring DKIM for {}", domain)

        opendkim_d = Dirpath("/etc/opendkim")
        keys_d = Dirpath(opendkim_d, "keys")
        keytable_f = Filepath(opendkim_d, "KeyTable")
        signingtable_f = Filepath(opendkim_d, "SigningTable")
        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")

        cli.run("opendkim-genkey --domain={} --verbose --directory=\"{}\"".format(
            domain.strip(),
            keys_d.path
        ))

        private_f = Filepath(keys_d, "default.private")
        private_f.rename("{}.private".format(domain))
        private_f.chmod(600)
        private_f.chown("opendkim:opendkim")

        txt_f = Filepath(keys_d, "default.txt")
        txt_f.rename("{}.txt".format(domain))

        keytable_f.append("default._domainkey.{} {}:default:{}\n".format(
            domain,
            domain,
            private_f.path
        ))

        signingtable_f.append("{} default._domainkey.{}\n".format(
            domain,
            domain
        ))

        trustedhosts_f.append("*.{}\n".format(domain))

        #for f in keys.d.files("\.txt$"):
        f = txt_f
        cli.print_out("*" * 80)
        cli.print_out("* YOU NEED TO ADD A DNS TXT RECORD FOR {}", domain)
        cli.print_out("* {}", f.path)
        cli.print_out("*" * 80)

        contents = f.contents()
        m = re.match("^(\S+)", contents)
        cli.print_out("* NAME: {}", m.group(1))
        cli.print_out("")

        mv = re.search("v=\S+", contents)
        mk = re.search("k=\S+", contents)
        mp = re.search("p=[^\"]+", contents)
        cli.print_out("* VALUE: {} {} {}", mv.group(0), mk.group(0), mp.group(0))

        cli.print_out("")
        cli.print_out("*" * 80)

    def configure_srs(self):

        # thanks to
        # http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
        # http://serverfault.com/questions/82234/srs-sender-rewriting-when-forwarding-mail-through-postfix
        # http://www.mind-it.info/2014/02/22/forward-postfix-spf-srs/
        # http://www.openspf.org/SRS

        cli.print_out("Configuring Postfix to use SRS")
        kwargs = self.kwargs

        cli.package("unzip", "cmake", "curl", "build-essential")

        # https://github.com/roehling/postsrsd
        cli.run("curl -L -o postsrsd.zip https://github.com/roehling/postsrsd/archive/master.zip", cwd="/tmp")
        cli.run("unzip -o postsrsd.zip", cwd="/tmp")

        # Build and install.
        build_d = Dirpath("/tmp/postsrsd-master/build")
        build_d.create()

        cli.run("cmake -DCMAKE_INSTALL_PREFIX=/usr ../", cwd=build_d.path)
        cli.run("make", cwd=build_d.path)
        cli.run("make install", cwd=build_d.path)

        m = Main(prototype_path=Main.dest_path)
        m.update(
            ("sender_canonical_maps", "tcp:localhost:10001"),
            ("sender_canonical_classes", "envelope_sender"),
            ("recipient_canonical_maps", "tcp:localhost:10002"),
            ("recipient_canonical_classes", "envelope_recipient,header_recipient")
        )
        m.save()

        cli.srs_reload()
        cli.postfix_reload()

    def lockdown(self):
        # http://www.cyberciti.biz/tips/postfix-spam-filtering-with-blacklists-howto.html
        # http://www.cyberciti.biz/faq/postfix-limit-incoming-or-receiving-email-rate/
        # https://www.debuntu.org/how-to-fight-spam-with-postfix-rbl/
        # https://www.howtoforge.com/virtual_postfix_antispam

        cli.print_out("Locking down Postfix")
        #self.assure_domain()
        self.assure_mailserver()
        kwargs = self.kwargs

        cli.print_out("getting external ip")
        external_ip = cli.ip()

        cli.print_out("configuring main")

        helo_f = Filepath("/etc/postfix/helo.regexp")
        helo_f.write("\n".join([
            "/^{}$/\t\t550 Don't use my own hostname".format(re.escape(kwargs["mailserver"])),
            "/^{}$/\t\t550 Don't use my own IP address".format(re.escape(external_ip)),
            "/^\[{}\]$/\t\t550 Don't use my own IP address".format(re.escape(external_ip)),
            "/^[0-9.]+$/\t\t\t550 Your software is not RFC 2821 compliant",
            "/^[0-9]+(\.[0-9]+){3}$/\t\t550 Your software is not RFC 2821 compliant",
            ""
        ]))

        main_f = Filepath(Main.dest_path)
        main_bak = main_f.backup(suffix=".bak.lockdown", ignore_existing=False)
        m = Main(prototype_path=main_bak.path)
        m.update(
            ("disable_vrfy_command", "yes"),
            ("smtpd_delay_reject", "yes"),
            ("smtpd_helo_required", "yes"),
            ("strict_rfc821_envelopes", "yes"),
            ("smtpd_helo_restrictions", ",\n    ".join([
                "permit_mynetworks",
                "permit_sasl_authenticated",
                "reject_non_fqdn_hostname",
                "reject_invalid_hostname",
                "regexp:/etc/postfix/helo.regexp",
                "permit"
            ])),
            ("smtpd_recipient_restrictions", ",\n    ".join([
                "permit_mynetworks",
                "permit_sasl_authenticated",
                "reject_invalid_hostname",
                "reject_non_fqdn_hostname",
                "reject_non_fqdn_sender",
                "reject_non_fqdn_recipient",
                "reject_unknown_sender_domain",
                "reject_unknown_recipient_domain",
                "reject_unauth_destination",
                "reject_unknown_reverse_client_hostname",
                "reject_rbl_client zen.spamhaus.org",
                "reject_rbl_client bl.spamcop.net",
                "reject_rbl_client cbl.abuseat.org",
                #"reject_rbl_client dul.dnsbl.sorbs.net,",
                "reject_rhsbl_sender dsn.rfc-ignorant.org",
                "permit"
            ])),
            ("smtpd_error_sleep_time", "1s"),
            ("smtpd_soft_error_limit", "10"),
            ("smtpd_hard_error_limit", "20")
        )
        m.save()

        cli.print_out("reloading postfix")
        cli.postfix_reload()

    def configure_greylist(self):
        # TODO -- not sure if want to enable this
        # https://www.debuntu.org/postfix-and-postgrey-a-proactive-approach-to-spam-filtering/
        # https://www.debuntu.org/postfix-and-postgrey-a-proactive-approach-to-spam-filtering-page-2/
        # https://github.com/schweikert/postgrey
        # http://serverfault.com/questions/701241/postgrey-whitelist-recipients-not-working
        # http://serverfault.com/questions/1817/does-smtp-greylisting-a-stop-much-spam-and-b-stop-much-legitimate-mail?rq=1
        # http://serverfault.com/questions/436327/is-greylisting-still-an-efficient-method-for-preventing-spam?rq=1
        # http://serverfault.com/questions/655924/possible-to-configure-postgrey-to-only-graylist-com-addresses
        pass



def main():
    '''
    cli hook

    return -- integer -- the exit code
    '''
    parser = argparse.ArgumentParser(description='Setup and manage an email proxy')
    names = [
        "setup",
        "install",
        "configure-recv",
        "configure-send",
        "configure-dkim",
        "configure-srs",
        "lockdown"
    ]
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

