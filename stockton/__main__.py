#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import argparse
import os
import subprocess
import re

from captain import echo, exit, ArgError
from captain.decorators import arg, args

from stockton import __version__, cli, dns
from stockton.concur.formats.postfix import Main, SMTPd, Master
from stockton.concur.formats.opendkim import OpenDKIM
from stockton.concur.formats.generic import SpaceConfig
from stockton.path import Dirpath, Filepath, Sentinal

from stockton.interface import SMTP, Postfix, DKIM


def main_prepare():
    echo.h2("Installing Postfix")

    with Sentinal.check("apt-get-update") as s:
        if not s:
            cli.run("apt-get update")

    #cli.run("apt-get -y install --no-install-recommends postfix")
    #cli.run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No configuration'\"")

    cli.package("postfix")


@arg('domain', default="", help='The email domain (eg, example.com)')
@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
@arg('--proxy-file', default="", help='The file containing domain addresses to proxy emails')
@arg('--proxy-email', default="", help='The final destination email address')
def main_configure_recv(domain, mailserver, proxy_file, proxy_email):
    # http://www.postfix.org/VIRTUAL_README.html

    echo.h2("Configuring Postfix to receive emails")

    p = Postfix()
    p.reset(really_delete_files=True)

    m = p.main("")
    m.update(
        ("alias_maps", "hash:/etc/aliases"), # http://unix.stackexchange.com/a/244200/118750
        ("myhostname", mailserver),
        #("mydomain", domain),
        #("myorigin", domain),
    )
    m.save()

    if domain:
        p.add_domain(domain, proxy_file, proxy_email)

    # make backup of master.cf
    master_bak = p.master_f.backup(ignore_existing=False)

    p.restart()


@arg('domain', help='The email domain (eg, example.com)')
@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg('--smtp-password', help='smtp password for sending emails')
@arg('--country', default="US", help='country for ssl certificate')
@arg('--state', help='state for ssl certificate')
@arg('--city', help='city for ssl certificate')
def main_configure_send(domain, mailserver, smtp_username, smtp_password, country, state, city):

    # https://help.ubuntu.com/lts/serverguide/postfix.html#postfix-sasl
    # http://www.postfix.org/SASL_README.html

    echo.h2("Configuring Postfix to send emails")

    cli.package("sasl2-bin", "libsasl2-modules")

    s = SMTP()
    s.add_user(smtp_username, smtp_password, domain)

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
    certs_key = Filepath(certs_d, "{}.key".format(mailserver))
    certs_crt = Filepath(certs_d, "{}.crt".format(mailserver))
    certs_pem = Filepath(certs_d, "{}.pem".format(mailserver))

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
        "-subj \"/C={}/ST={}/L={}/O={}/CN={}\"".format(
            country,
            state,
            city,
            mailserver,
            mailserver
        ),
        "-keyout {}".format(certs_key),
        "-out {}".format(certs_crt)
    ]))
    cli.run("cat {} {} > {}".format(certs_crt, certs_key, certs_pem))

    # make backup of master.cf if it doesn't already exist
    master_f = Filepath(Master.dest_path)
    master_bak = master_f.backup(ignore_existing=False)

    # add the config to master.cf to enable smtp sending
    m = Master(prototype_path=master_bak.path)
    for smtp in m["smtp"]:
        if smtp.cmd == "smtpd":
            smtp.chroot = "n"

    m["submission"].chroot = "n"
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


def main_configure_dkim():
    """DomainKeys Identified Mail (DKIM)

    Setup dkim support

    http://www.dkim.org/
    """

    # setup for multi-domain support thanks to
    # http://askubuntu.com/questions/438756/using-dkim-in-my-server-for-multiple-domains-websites
    # http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
    # http://edoceo.com/howto/opendkim
    # https://help.ubuntu.com/community/Postfix/DKIM

    echo.h2("Configuring Postfix to use DKIM")

    cli.package("opendkim", "opendkim-tools")

    dk = DKIM()
    opendkim_d = dk.opendkim_d
    opendkim_d.create()
    opendkim_d.clear()

    keys_d = dk.keys_d
    keys_d.create()
    keys_d.clear()

    hosts = [
        "127.0.0.1",
        "::1",
        "localhost",
        "192.168.0.1/24",
    ]
    # could also use https://pypi.python.org/pypi/netifaces but this seemed easier
    # http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    external_ip = cli.ip()
    if external_ip:
        hosts.append(external_ip)

    hosts.append("")
    trustedhosts_f = dk.trustedhosts_f
    trustedhosts_f.writelines(hosts)
    #trustedhosts_f = opendkim_d.create_file("TrustedHosts", "\n".join(hosts))

    keytable_f = dk.keytable_f
    signingtable_f = dk.signingtable_f

    # make backup of config
    config_f = dk.config_f
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

    p = Postfix()
    m = p.main()
    m.update(
        ("milter_default_action", "accept"),
        # http://lists.opendkim.org/archive/opendkim/users/2011/08/1297.html
        ("milter_protocol", "6"),
        ("smtpd_milters", "inet:localhost:8891"),
        ("non_smtpd_milters", "inet:localhost:8891"),
    )
    m.save()

    # http://unix.stackexchange.com/a/74491/118750
    cli.run("adduser postfix opendkim")

    dk.add_domains()

    p.restart()
    dk.restart()


def main_configure_srs():
    """SRS: Sender Rewriting Scheme

    This configures SRS so SPF will work correctly and treat this MTA as a proxy

    http://www.openspf.org/SRS
    """

    # thanks to
    # http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
    # http://serverfault.com/questions/82234/srs-sender-rewriting-when-forwarding-mail-through-postfix
    # http://www.mind-it.info/2014/02/22/forward-postfix-spf-srs/
    # http://www.openspf.org/SRS

    echo.h2("Configuring Postfix to use SRS")

    cli.package("unzip", "cmake", "curl", "build-essential")

    tmpdir = Dirpath.get_temp()

    # only download the srs if it doesn't already exist
    postsrs_f = Filepath(tmpdir, "postsrsd.zip")
    with Sentinal.check("srs") as s:
        if not s:
            # https://github.com/roehling/postsrsd
            cli.run("curl -L -o postsrsd.zip https://github.com/roehling/postsrsd/archive/master.zip", cwd=tmpdir.path)

        else:
            echo.out("****** not downloading postsrsd because sentinal {}", s)

    # Build and install.
    cli.run("unzip -o postsrsd.zip", cwd=tmpdir.path)
    build_d = Dirpath(tmpdir, "postsrsd-master", "build")
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


@arg('domain', help='The email domain to remove (eg, example.com)')
def main_delete_domain(domain):
    """remove a domain from the server"""
    echo.h3("Deleting domain {}", domain)

    # TODO -- most of this should be moved to postfix.py and dkim.py files

    m = Main(prototype_path=Main.dest_path)

    # remove postfix settings
    virtual_d = Dirpath("/etc/postfix/virtual")

    domains_f = Filepath(virtual_d, "domains")
    domains_f.delete_lines("^{}$".format(domain))

    addresses_d = Dirpath(virtual_d, "addresses")
    addresses_d.delete_files("^{}".format(domain))

    domain_hashes = []
    for d in domains_f.lines():
        domain_f = Filepath(addresses_d, d)
        domain_hashes.append("hash:{}".format(domain_f.path))

    m = Main(prototype_path=Main.dest_path)
    m["virtual_alias_maps"] = ",\n  ".join(domain_hashes)
    m.save()

    # make sure lockdown is still idempotent
    main_f = Filepath(Main.dest_path)
    main_bak = main_f.backup(suffix=".lockdown.bak", ignore_existing=True)

    # remove dkim settings
    opendkim_d = Dirpath("/etc/opendkim")

    signingtable_f = Filepath(opendkim_d, "SigningTable")
    signingtable_f.delete_lines(domain)

    trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
    trustedhosts_f.delete_lines(domain)

    cli.postfix_reload()
    cli.opendkim_reload()


@arg('domain', default="", help='The email domain (eg, example.com)')
@arg('--proxy-file', default="", help='The file containing domain addresses to proxy emails')
#@arg('--proxy-domains', default="", help='The directory containing domain configuration files')
@arg('--proxy-email', default="", help='The final destination email address')
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg('--smtp-password', default="", help='smtp password for sending emails')
def main_add_domain(domain, proxy_file, proxy_email, smtp_username, smtp_password):

    p = Postfix()
    p.add_domain(domain, proxy_file, proxy_email)

    dk = DKIM()
    dk.add_domain(domain)

    if smtp_password:
        s = SMTP()
        s.add_user(smtp_username, smtp_password, domain)

    p.restart()
    dk.restart()

    main_check_domain(domain)


def main_dkim_genkeys():
    dk = DKIM()
    p = Postfix()
    domains_f = Filepath("/etc/postfix/virtual/domains")
    for domain in p.domains:
        dk.add_domain(domain, gen_key=True)
        main_check_domain(domain, ["dkim"])

    p.restart()
    dk.restart()


def disabled_configure_greylist(self):
    # TODO -- not sure if want to enable this
    # https://www.debuntu.org/postfix-and-postgrey-a-proactive-approach-to-spam-filtering/
    # https://www.debuntu.org/postfix-and-postgrey-a-proactive-approach-to-spam-filtering-page-2/
    # https://github.com/schweikert/postgrey
    # http://serverfault.com/questions/701241/postgrey-whitelist-recipients-not-working
    # http://serverfault.com/questions/1817/does-smtp-greylisting-a-stop-much-spam-and-b-stop-much-legitimate-mail?rq=1
    # http://serverfault.com/questions/436327/is-greylisting-still-an-efficient-method-for-preventing-spam?rq=1
    # http://serverfault.com/questions/655924/possible-to-configure-postgrey-to-only-graylist-com-addresses
    pass


@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
def main_lockdown(mailserver):
    # http://www.cyberciti.biz/tips/postfix-spam-filtering-with-blacklists-howto.html
    # http://www.cyberciti.biz/faq/postfix-limit-incoming-or-receiving-email-rate/
    # https://www.debuntu.org/how-to-fight-spam-with-postfix-rbl/
    # https://www.howtoforge.com/virtual_postfix_antispam

    echo.h2("Locking down Postfix")

    # make sure we've got a backup before we start messing with stuff, we won't
    # create a backup if it already exists
    main_f = Filepath(Main.dest_path)
    main_bak = main_f.backup(suffix=".lockdown.bak", ignore_existing=False)

    external_ip = cli.ip()

    echo.h3("configuring main")

    helo_f = SpaceConfig(dest_path="/etc/postfix/helo.regexp")
    helo_f.update(
        ("/^{}$/".format(re.escape(mailserver)), "550 Don't use my own hostname"),
        ("/^{}$/".format(re.escape(external_ip)), "550 Don't use my own IP address"),
        ("/^\[{}\]$/".format(re.escape(external_ip)), "550 Don't use my own IP address"),
        ("/^[0-9.]+$/", "550 Your software is not RFC 2821 compliant"),
        ("/^[0-9]+(\.[0-9]+){3}$/", "550 Your software is not RFC 2821 compliant")
    )
    helo_f.save()

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
            "reject_rbl_client b.barracudacentral.org",
            #"reject_rbl_client cbl.abuseat.org",
            #"reject_rbl_client dul.dnsbl.sorbs.net,",
            #"reject_rhsbl_sender dsn.rfc-ignorant.org",
            "permit"
        ])),
        ("smtpd_error_sleep_time", "1s"),
        ("smtpd_soft_error_limit", "10"),
        ("smtpd_hard_error_limit", "20")
    )
    m.save()

    # dbl.spamhaus.org
    # xbl.spamhaus.org
    # b.barracudacentral.org
    # http://serverfault.com/a/514830/190381

    cli.postfix_reload()

# TODO -- I have renamed main_check_domains to domain, so things need to be fixed
# the add-domain should take a domain-addresses and there should be a new command
# add-domains that take an addresses dir (what is proxy-domains


@arg('domain', help='The domain whose dns will be checked (eg, example.com)')
@arg(
    '--record', "-r",
    action="append",
    dest="records",
    help='records to check',
    default=None,
    choices=["mx", "a", "ptr", "spf", "dkim"],
)
def main_check_domain(domain, records=None):
    if not records:
        records = ["mx", "a", "ptr", "spf", "dkim"]

    pf = Postfix()
    mailserver = pf.mailserver
    external_ip = cli.ip()

    def print_record(name, domain, records):
        if records:
            echo.h1("DNS {} RECORD NEEDED FOR {}", name, domain)
            echo.br()

            echo.columns(*zip(*records))
            echo.br()

        else:
            echo.h3("{} record found", name)
            echo.br()

    if "a" in records:
        d = dns.Mailserver(mailserver, external_ip)
        print_record("A", mailserver, d.needed_a())

    if "ptr" in records:
        d = dns.Mailserver(mailserver, external_ip)
        print_record("PTR", mailserver, d.needed_ptr())

    if "mx" in records:
        d = dns.Alias(domain, mailserver)
        print_record("MX", domain, d.needed_mx())

    if "spf" in records:
        d = dns.Alias(domain, mailserver)
        print_record("SPF", domain, d.needed_spf())

    if "dkim" in records:
        try:
            d = dns.Alias(domain, mailserver)
            print_record("DKIM", domain, d.needed_dkim())
        except IOError:
            echo.h3("No local DKIM key found for {}", domain)


@args(main_configure_recv, main_configure_send)
def main_install(domain, mailserver, smtp_username, smtp_password, country, state, city, proxy_domains, proxy_email):

    main_prepare()
    main_configure_recv(domain, mailserver, proxy_domains, proxy_email)
    main_configure_send(domain, mailserver, smtp_username, smtp_password, country, state, city)
    main_configure_dkim()
    main_configure_srs()
    main_lockdown(mailserver)
    main_check_domain(domain)


def console():
    """we wrap captain.exit() so we can check for root"""
    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run command with sudo")

    exit()

console()

