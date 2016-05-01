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

from stockton.interface import SMTP, Postfix, PostfixCert, DKIM, Spam


def main_prepare():
    echo.h2("Installing Postfix")

    with Sentinal.check("apt-get-update") as s:
        if not s:
            cli.run("apt-get update")

    #cli.run("apt-get -y install --no-install-recommends postfix")
    #cli.run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No configuration'\"")

    cli.package("postfix")


@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
@arg('--update', action="store_true", help='Update settings instead of replace them')
def main_configure_recv(mailserver, update):
    """Configure Postfix mailserver to receive email

    NOTE -- this doesn't actually configure any domains, in order to actually receive
    emails you should use add-domain(s)
    """
    # http://www.postfix.org/VIRTUAL_README.html

    echo.h2("Configuring Postfix to receive emails")

    p = Postfix()

    if not update:
        p.reset(really_delete_files=True)

    cert = PostfixCert(mailserver)
    cert.assure()

    settings = [
        ("alias_maps", "hash:/etc/aliases"), # http://unix.stackexchange.com/a/244200/118750
        ("myhostname", mailserver),
    ]

    # Smtpd means mails you receive from outside, smtp covers mails you send to other servers
    # http://blog.snapdragon.cc/2013/07/07/setting-postfix-to-encrypt-all-traffic-when-talking-to-other-mailservers/

    # Incoming
    settings.extend([
        ("smtpd_tls_cert_file", cert.crt),
        ("smtpd_tls_key_file", cert.key),
        ("smtpd_use_tls", "yes"),
        ("smtpd_tls_auth_only", "yes"),
        ("smtpd_tls_security_level", "may"),
        ("smtpd_tls_loglevel", 1),
        ("smtpd_tls_mandatory_ciphers", "high"),
        ("smtpd_tls_mandatory_protocols", "!SSLv2, !SSLv3"),
        ("smtpd_tls_session_cache_database", "btree:${data_directory}/smtpd_scache"),
    ])

    # Outgoing
    settings.extend([
        ("smtp_tls_cert_file", cert.crt),
        ("smtp_tls_key_file", cert.key),
        ("smtp_use_tls", "yes"),
        ("smtp_tls_security_level", "may"),
        ("smtp_tls_loglevel", 1),
        ("smtp_tls_mandatory_ciphers", "high"),
        ("smtp_tls_mandatory_protocols", "!SSLv2, !SSLv3"),
        ("smtp_tls_session_cache_database", "btree:${data_directory}/smtp_scache"),
    ])

    m = p.main_live if update else p.main_new
    m.update(*settings)
    m.save()

    # make backup of master.cf
    master_bak = p.master_f.backup(ignore_existing=False)

    if update:
        for mbak in p.main_backups():
            mbak.update(*settings)
            mbak.save()

    p.restart()


@arg('domain', help='The email domain (eg, example.com)')
@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg('--smtp-password', help='smtp password for sending emails')
def main_configure_send(domain, mailserver, smtp_username, smtp_password):

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

    cert = PostfixCert(mailserver)
    cert.assure()

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
        ("smtpd_tls_cert_file", cert.pem.path),
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

    dk = DKIM()
    opendkim_d = dk.opendkim_d
    opendkim_d.clear()

    keys_d = dk.keys_d
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


@arg(
    '--proxy-domains',
    type=Dirpath,
    help='Directory containing domain configuration files'
)
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg(
    '--smtp-password',
    default="",
    help='smtp password for sending emails, will be used for each domain in proxy-domains'
)
def main_add_domains(proxy_domains, smtp_username, smtp_password):
    """add-domains

    Given a directory containing domain alias configuration files, corresponding to
    the format specified in

    http://www.postfix.org/virtual.5.html

    Add each of the domains to Postfix, if smtp-password is given, then also set
    up the virtual domain to be able to send email.
    """
    domains = {}
    for proxy_f in proxy_domains.files():
        domain_check = set()
        for line in proxy_f:
            m = re.match("^(\S*@\S+)", line)
            if m:
                bits = m.group(1).split("@", 1)
                if len(bits) == 2:
                    domain_check.add(bits[1])

        if len(domain_check) == 1:
            domain = domain_check.pop()
            if domain in domains:
                raise ValueError("proxy_file {} contains domain {} also seen in {}".format(
                    proxy_f,
                    domain,
                    domains[domain],
                ))

            domains[domain] = proxy_f

        else:
            raise ValueError("Found multiple domains in proxy_file {}".format(proxy_f))

    for domain, proxy_file in domains.items():
        echo.h2("Adding domain {} from file {}", domain, proxy_file)
        main_add_domain(domain, proxy_file, "", smtp_username, smtp_password)


@arg('domain', help='The email domain (eg, example.com)')
@arg('--proxy-file', default="", help='The file containing domain addresses to proxy emails')
#@arg('--proxy-domains', default="", help='The directory containing domain configuration files')
@arg('--proxy-email', default="", help='The final destination email address')
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg('--smtp-password', default="", help='smtp password for sending emails')
def main_add_domain(domain, proxy_file, proxy_email, smtp_username, smtp_password):
    """add-domain

    add one virtual domain to postfix
    """
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


@arg('domain', help='The email domain (eg, example.com)')
def main_gen_domain_key(domain):
    """re-generate the DKIM key for domain"""
    p = Postfix()
    dk = DKIM()
    dk.add_domain(domain, gen_key=True)
    main_check_domain(domain, ["dkim"])
    p.restart()
    dk.restart()



@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
def main_lockdown_postfix(mailserver):
    # http://www.cyberciti.biz/tips/postfix-spam-filtering-with-blacklists-howto.html
    # http://www.cyberciti.biz/faq/postfix-limit-incoming-or-receiving-email-rate/
    # https://www.debuntu.org/how-to-fight-spam-with-postfix-rbl/
    # https://www.howtoforge.com/virtual_postfix_antispam

    echo.h2("Locking down Postfix")

    p = Postfix()

    # make sure we've got a backup before we start messing with stuff, we won't
    # create a backup if it already exists
    main_f = p.main_f
    main_bak = main_f.backup(suffix=".lockdown.bak", ignore_existing=False)

    external_ip = cli.ip()

    echo.h3("configuring main")

    h = p.helo
    h.update(
        ("/^{}$/".format(re.escape(mailserver)), "550 Don't use my own hostname"),
        ("/^{}$/".format(re.escape(external_ip)), "550 Don't use my own IP address"),
        ("/^\[{}\]$/".format(re.escape(external_ip)), "550 Don't use my own IP address"),
        ("/^[0-9.]+$/", "550 Your software is not RFC 2821 compliant"),
        ("/^[0-9]+(\.[0-9]+){3}$/", "550 Your software is not RFC 2821 compliant")
    )
    h.save()

    m = p.main(main_bak.path)
    m.update(
        ("disable_vrfy_command", "yes"),
        ("smtpd_delay_reject", "yes"),
        ("strict_rfc821_envelopes", "yes"),
        ("smtpd_helo_required", "yes"),
        ("smtpd_helo_restrictions", ",\n    ".join([
            "permit_mynetworks",
            "permit_sasl_authenticated",
            "reject_non_fqdn_hostname",
            "reject_invalid_hostname",
            "regexp:{}".format(p.helo_f.path),
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

            # from: http://www.akadia.com/services/postfix_spamassassin.html
            #reject_unauth_pipelining,
            #check_client_access hash:$config_directory/access_client,
            #check_sender_access hash:$config_directory/access_sender

            # disabled for spam assassin
            #"reject_rbl_client zen.spamhaus.org",
            #"reject_rbl_client bl.spamcop.net",
            #"reject_rbl_client b.barracudacentral.org",
            # disabled previously
            #"reject_rbl_client cbl.abuseat.org",
            #"reject_rbl_client dul.dnsbl.sorbs.net,",
            #"reject_rhsbl_sender dsn.rfc-ignorant.org",
            "permit"
        ])),

        # incoming
        ("smtpd_error_sleep_time", "1s"),
        ("smtpd_soft_error_limit", "10"),
        ("smtpd_hard_error_limit", "20"),

        # outgoing
        # This means that postfix will up to two concurrent
        # connections per receiving domains. The default value is 20.
        ("smtp_destination_concurrency_limit", 2),
        # Postfix will add a delay between each message to the same receiving domain.
        # It overrides the previous rule and in this example, it will send one email
        # after another with a delay of 1 second.
        ("smtp_destination_rate_delay", "5s"),
        # Limit the number of recipients of each message. If a message had 20 recipients
        # on the same domain, postfix will break it out to two different email messages instead of one.
        ("smtp_extra_recipient_limit", 10),
    )
    m.save()

    # dbl.spamhaus.org
    # xbl.spamhaus.org
    # b.barracudacentral.org
    # http://serverfault.com/a/514830/190381

    p.restart()


def main_lockdown_spam():
    s = Spam()
    s.install()

    config_bak = s.config_f.backup(ignore_existing=False)
    c = s.config(config_bak.path)
    c.update(
        ("ENABLED", 1),
        ("OPTIONS", '"--create-prefs --max-children 5 --username {} --helper-home-dir {} -s /var/log/spamd.log"'.format(
            s.user,
            s.home_d
        )),
        ("CRON", 1)
    )
    c.save()

    local_bak = s.local_f.backup(ignore_existing=False)
    c = s.local(local_bak.path)
    c.update(
        ("rewrite_header", "Subject SPAM _SCORE_ *"),
        ("report_safe", 0),
        ("required_score", 5.0),
        ("use_bayes", 1),
        ("use_bayes_rules", 1),
        ("bayes_auto_learn", 1),
        ("skip_rbl_checks", 0),
        ("use_razor2", 0),
        ("use_dcc", 0),
        ("use_pyzor", 0),
    )
    c.save()

    # make backup of master.cf if it doesn't already exist
    p = Postfix()
    master_f = p.master_f
    master_bak = master_f.backup(".lockdown.bak", ignore_existing=False)
    m = p.master(master_bak.path)

    # add the config to master.cf to enable smtp sending
    m = Master(prototype_path=master_bak.path)
    for smtp in m["smtp"]:
        if smtp.cmd == "smtpd":
            smtp.update(
                ("content_filter", "spamassassin")
            )

    section = m.create_section("spamassassin unix - n n - - pipe")
    section.update(
        "user=spamd argv=/usr/bin/spamc -f -e",
        "/usr/sbin/sendmail -oi -f ${sender} ${recipient}",
    )
    m["spamassassin"] = section
    m.save()

    p.restart()
    s.restart()


@args(main_lockdown_postfix, main_lockdown_spam)
def main_lockdown(mailserver):
    main_lockdown_postfix(mailserver)
    main_lockdown_spam()


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
def main_install(domain, mailserver, smtp_username, smtp_password, proxy_domains, proxy_email):

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

if __name__ == "__main__":
    console()

