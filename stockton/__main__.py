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

from stockton.interface import SMTP, Postfix, DKIM, Spam, SRS


def main_prepare():
    """Get a server ready to configure postfix by installing postfix"""
    echo.h2("Installing Postfix")

    with Sentinal.check("apt-get-update") as s:
        if not s:
            cli.run("apt-get update")

    #cli.run("apt-get -y install --no-install-recommends postfix")
    #cli.run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No configuration'\"")
    p = Postfix()
    p.install()


@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
def main_configure_recv(mailserver):
    """Configure Postfix mailserver to receive email

    NOTE -- this doesn't actually configure any domains, in order to actually receive
    emails you should use add-domain(s)
    """
    # http://www.postfix.org/VIRTUAL_README.html

    echo.h2("Configuring Postfix to receive emails")

    p = Postfix()
    cert = p.cert(mailserver)
    cert.assure()

    settings = [
        ("alias_maps", "hash:/etc/aliases"), # http://unix.stackexchange.com/a/244200/118750
        ("myhostname", mailserver),
    ]

    # Smtpd means mails you receive from outside, smtp covers mails you send to other servers
    # http://blog.snapdragon.cc/2013/07/07/setting-postfix-to-encrypt-all-traffic-when-talking-to-other-mailservers/

    # Incoming
    settings.extend([
        ("smtpd_tls_cert_file", cert.crt_f.path),
        ("smtpd_tls_key_file", cert.key_f.path),
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
        ("smtp_tls_cert_file", cert.crt_f.path),
        ("smtp_tls_key_file", cert.key_f.path),
        ("smtp_use_tls", "yes"),
        ("smtp_tls_security_level", "may"),
        ("smtp_tls_loglevel", 1),
        ("smtp_tls_mandatory_ciphers", "high"),
        ("smtp_tls_mandatory_protocols", "!SSLv2, !SSLv3"),
        ("smtp_tls_session_cache_database", "btree:${data_directory}/smtp_scache"),
    ])

    m = p.main()
    m.update(*settings)
    m.save()

    p.restart()


@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
def main_configure_send(mailserver):
    """Configure postfix to handle smtp connections so you can send mail"""

    # https://help.ubuntu.com/lts/serverguide/postfix.html#postfix-sasl
    # http://www.postfix.org/SASL_README.html

    echo.h2("Configuring Postfix to send emails")

    p = Postfix()
    s = SMTP()

    s.install()

    c = s.config
    c.update(
        ("pwcheck_method", "auxprop"),
        ("auxprop_plugin", "sasldb"),
        ("mech_list", "PLAIN LOGIN CRAM-MD5 DIGEST-MD5 NTLM"),
        ("log_level", "7")
    )
    c.save()

    cert = p.cert(mailserver)
    cert.assure()

    #master_f = p.master_f
    #master_bak = p.base_create("send", [master_f])[0]

    # add the config to master.cf to enable smtp sending
    #m = p.master(master_bak.path)
    m = p.master()
    for smtp in m["smtp"]:
        if smtp.cmd == "smtpd":
            smtp.chroot = "n"

    m["submission"].chroot = "n"
    m["submission"].update(
        ("syslog_name", "postfix/submission"),
        ("smtpd_tls_security_level", "may"),
        ("smtpd_tls_cert_file", cert.pem_f.path),
        ("smtpd_sasl_auth_enable", "yes"),
        ("smtpd_reject_unlisted_recipient", "no"),
        ("smtpd_relay_restrictions", "permit_sasl_authenticated,reject"),
        ("milter_macro_daemon_name", "ORIGINATING")
    )
    m.save()

    p.restart()


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
    p = Postfix()

    dk.install()

    # could also use https://pypi.python.org/pypi/netifaces but this seemed easier
    # http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    external_ip = cli.ip()
    if external_ip:
        dk.set_ip(external_ip)

    trustedhosts_f = dk.trustedhosts_f
    c = dk.config()
    c.update(
        ("Canonicalization", "relaxed/simple"),
        ("Mode", "sv"),
        ("SubDomains", "yes"),
        ("Syslog", "yes"),
        ("LogWhy", "yes"),
        ("UMask", "022"),
        ("UserID", "opendkim:opendkim"),
        ("KeyTable", dk.keytable_f.path),
        ("SigningTable", dk.signingtable_f.path),
        ("ExternalIgnoreList", trustedhosts_f.path),
        ("InternalHosts", trustedhosts_f.path),
        ("Socket", "inet:8891@localhost")
    )
    c.save()

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

    echo.h2("Configuring Postfix to use SRS")

    s = SRS()
    p = Postfix()

    s.install()

    m = p.main()
    m.update(
        ("sender_canonical_maps", "tcp:localhost:10001"),
        ("sender_canonical_classes", "envelope_sender"),
        ("recipient_canonical_maps", "tcp:localhost:10002"),
        ("recipient_canonical_classes", "envelope_recipient,header_recipient")
    )
    m.save()

    s.restart()
    p.restart()


@arg('domain', help='The email domain to remove (eg, example.com)')
def main_delete_domain(domain):
    """remove a domain from the server"""
    echo.h3("Deleting domain {}", domain)

    # remove postfix settings
    p = Postfix()
    p.delete_domain(domain)

    # remove dkim settings
    dk = DKIM()
    dk.delete_domain(domain)

    p.restart()
    dk.restart()


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
    p = Postfix()
    domains = {}
    for proxy_f in proxy_domains.files():
        domain = p.autodiscover_domain(proxy_f)
        if domain in domains:
            raise ValueError("proxy_file {} contains domain {} also seen in {}".format(
                proxy_f,
                domain,
                domains[domain],
            ))

        domains[domain] = proxy_f

    for domain, proxy_file in domains.items():
        echo.h2("Adding domain {} from file {}", domain, proxy_file)
        main_add_domain(domain, proxy_file, "", smtp_username, smtp_password)


@arg('domain', nargs="?", help='The email domain (eg, example.com)')
@arg('--proxy-file', default="", help='The file containing domain addresses to proxy emails')
@arg('--proxy-email', default="", help='The final destination email address')
@arg('--smtp-username', default="smtp", help='smtp username for sending emails')
@arg('--smtp-password', default="", help='smtp password for sending emails')
def main_add_domain(domain, proxy_file, proxy_email, smtp_username, smtp_password):
    """add-domain

    add one virtual domain to postfix
    """
    p = Postfix()

    if not domain:
        domain = p.autodiscover_domain(proxy_file)

    p.add_domain(domain, proxy_file, proxy_email)

    echo.h3("Configuring DKIM for {}", domain)
    dk = DKIM()
    if dk.exists():
        dk.add_domain(domain)
        dk.restart()

    if smtp_password:
        s = SMTP()
        s.add_user(smtp_username, smtp_password, domain)

    p.restart()
    main_check_domain(domain)


@arg('domain', help='The email domain (eg, example.com)')
def main_gen_domain_key(domain):
    """re-generate the DKIM key for the domain"""
    p = Postfix()
    dk = DKIM()
    dk.add_domain(domain, gen_key=True)
    main_check_domain(domain, ["dkim"])
    p.restart()
    dk.restart()


@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
def main_lockdown_postfix(mailserver):
    """Tighten the postfix restrictions for sending and receiving email"""
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
    """Install SpamAssassin and configure postfix to use it"""
    s = Spam()
    s.install()

    c = s.config()
    c.update(
        ("ENABLED", 1),
        ("OPTIONS", '"--create-prefs --max-children 5 --username {} --helper-home-dir {} -s /var/log/spamd.log"'.format(
            s.user,
            s.home_d
        )),
        ("CRON", 1)
    )
    c.save()

    c = s.local()
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
#     master_bak = p.base_create("spam", [p.master_f])[0]
#     m = p.master(master_bak)
    m = p.master()

    # add the config to master.cf to enable smtp sending
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
    """Run all the lockdown commands"""
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


@args(main_configure_recv, main_add_domains, main_add_domain)
@arg('--proxy-domains', default="")
def main_install(**kwargs):
    """Install, configure, and lockdown a postfix server"""
    main_prepare()
    main_configure_recv(mailserver=kwargs["mailserver"])
    main_configure_send(mailserver=kwargs["mailserver"])

    main_configure_dkim()
    main_configure_srs()
    main_lockdown(mailserver=kwargs["mailserver"])

    if kwargs["proxy_domains"]:
        main_add_domains(
            proxy_domains=kwargs["proxy_domains"],
            smtp_username=kwargs["smtp_username"],
            smtp_password=kwargs["smtp_password"]
        )

    else:
        main_add_domain(
            domain=kwargs["domain"],
            proxy_file=kwargs["proxy_file"],
            proxy_email=kwargs["proxy_email"],
            smtp_username=kwargs["smtp_username"],
            smtp_password=kwargs["smtp_password"]
        )


def main_uninstall():
    """Completely remove the postfix server from"""
    echo.h2("Uninstalling Mail Server")

    echo.h3("Removing SpamAssassin")
    sp = Spam()
    sp.uninstall()

    echo.h3("Removing SRS")
    sr = SRS()
    sr.uninstall()

    echo.h3("Removing DKIM")
    dk = DKIM()
    dk.uninstall()

    echo.h3("Removing SMTP")
    sm = SMTP()
    sm.uninstall()

    echo.h3("Removing Postfix")
    p = Postfix()
    p.uninstall()


def console():
    """we wrap captain.exit() so we can check for root"""
    if len(sys.argv) > 1 and "--help" not in sys.argv and "-h" not in sys.argv:
        if os.environ["USER"] != "root":
            raise RuntimeError("User is not root, re-run command with sudo")

    exit()

if __name__ == "__main__":
    console()

