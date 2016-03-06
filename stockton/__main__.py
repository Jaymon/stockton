#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import argparse
import os
import subprocess
import re

from captain import echo, exit, ArgError
from captain.decorators import arg

from stockton import __version__, cli
from stockton.concur.formats.postfix import Main, SMTPd, Master
from stockton.concur.formats.opendkim import OpenDKIM
from stockton.concur.formats.generic import SpaceConfig
from stockton.path import Dirpath, Filepath, Sentinal


@arg('--domain', dest='domain', default="", help='The email domain (eg, example.com)')
@arg('--mailserver', dest='mailserver', default="", help='The domain mailserver (eg, mail.example.com)')
def main_setup():
    # TODO -- if postfix is already installed then bak files need to be cleared, etc
    # the key is re-running should be idempotent

    main_install()
    main_configure_recv()
    main_configure_send()
    self.configure_dkim()
    self.configure_srs()
    #self.lockdown()


def main_install():
    echo.h2("Installing Postfix")

    with Sentinal.check("apt-get-update") as s:
        if not s:
            cli.run("apt-get update")

    #cli.run("apt-get -y install --no-install-recommends postfix")
    #cli.run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No configuration'\"")

    cli.package("postfix")


@arg('--domain', help='The email domain (eg, example.com)')
@arg('--mailserver', help='The domain mailserver (eg, mail.example.com)')
@arg('--proxy-domains', default="", help='The directory containing domain configuration files')
@arg('--proxy-email', default="", help='The final destination email address')
def main_configure_recv(domain, mailserver, proxy_domains, proxy_email):
    # http://www.postfix.org/VIRTUAL_README.html

    echo.h2("Configuring Postfix to receive emails")

    # remove any .bak files in this directory, we do this to make sure any other
    # commands that configure postfix will be able to make correct snapshots of
    # the main.cf file to remain idempotent
    postfix_d = Dirpath("/etc/postfix")
    for f in postfix_d.files(".bak$"):
        f.delete()

    virtual_d = Dirpath("/etc/postfix/virtual")
    echo.h3("Clearing {}", virtual_d)
    virtual_d.clear()

    m = Main()
    m.update(
        ("myhostname", mailserver),
        ("mydomain", domain),
        ("myorigin", domain),
    )
    m.save()

    add_postfix_domains(domain, proxy_domains, proxy_email)

    # make backup of master.cf
    master_f = Filepath(Master.dest_path)
    master_bak = master_f.backup(ignore_existing=False)

    cli.postfix_reload()


@arg('--domain', help='The email domain (eg, example.com)')
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

    cli.run("echo \"{}\" | saslpasswd2 -c -u {} {} -p".format(smtp_password, mailserver, smtp_username))

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
    certs_key = Filepath(certs_d, "{}.key".format(domain))
    certs_crt = Filepath(certs_d, "{}.crt".format(domain))
    certs_pem = Filepath(certs_d, "{}.pem".format(domain))

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

    # setup for multi-domain support thanks to
    # http://askubuntu.com/questions/438756/using-dkim-in-my-server-for-multiple-domains-websites
    # http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
    # http://edoceo.com/howto/opendkim
    # https://help.ubuntu.com/community/Postfix/DKIM

    echo.h2("Configuring Postfix to use DKIM")

    cli.package("opendkim", "opendkim-tools")

    opendkim_d = Dirpath("/etc/opendkim")
    opendkim_d.create()
    opendkim_d.clear()

    keys_d = Dirpath(opendkim_d, "keys")
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

    add_dkim_domains()

    cli.postfix_reload()
    cli.opendkim_reload()


def main_configure_srs():

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
            echo.out("****** not downloading postsrsd because sentinal {}", execute)

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





@arg('--domain', default="", help='The email domain (eg, example.com)')
@arg('--proxy-domains', default="", help='The directory containing domain configuration files')
@arg('--proxy-email', default="", help='The final destination email address')
def main_add_domain(domain, proxy_domains, proxy_email):
    add_postfix_domains(domain, proxy_domains, proxy_email)
    add_dkim_domains()

    cli.postfix_reload()
    cli.opendkim_reload()


def add_dkim_domains():

#     opendkim_d = Dirpath("/etc/opendkim")
#     keys_d = Dirpath(opendkim_d, "keys")
#     keytable_f = Filepath(opendkim_d, "KeyTable")
#     keytable_f.clear()
#     signingtable_f = Filepath(opendkim_d, "SigningTable")
#     signingtable_f.clear()
#     trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
#     trustedhosts_f.clear()

    domains_f = Filepath("/etc/postfix/virtual/domains")
    for domain in domains_f.lines():
        add_dkim_domain(domain)


def add_dkim_domain(domain):
    echo.h3("Configuring DKIM for {}", domain)

    is_new_domain = False
    opendkim_d = Dirpath("/etc/opendkim")
    keys_d = Dirpath(opendkim_d, "keys")
    keytable_f = Filepath(opendkim_d, "KeyTable")
    signingtable_f = Filepath(opendkim_d, "SigningTable")
    trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")

    private_f = Filepath(keys_d, "{}.private".format(domain))
    txt_f = Filepath(keys_d, "{}.txt".format(domain))
    if not txt_f.exists():
        is_new_domain = True
        #cli.run("opendkim-genkey --domain={} --verbose --directory=\"{}\"".format(
        cli.run("opendkim-genkey --domain={} --directory=\"{}\"".format(
            domain,
            keys_d.path
        ))

        private_f = Filepath(keys_d, "default.private")
        private_f.rename("{}.private".format(domain))
        private_f.chmod(600)
        private_f.chown("opendkim:opendkim")

        txt_f = Filepath(keys_d, "default.txt")
        txt_f.rename("{}.txt".format(domain))

    if not keytable_f.contains(domain):
        is_new_domain = True
        keytable_f.append("default._domainkey.{} {}:default:{}\n".format(
            domain,
            domain,
            private_f.path
        ))

    if not signingtable_f.contains(domain):
        is_new_domain = True
        signingtable_f.append("{} default._domainkey.{}\n".format(
            domain,
            domain
        ))

    if not trustedhosts_f.contains(domain):
        is_new_domain = True
        trustedhosts_f.append("*.{}\n".format(domain))

    echo.banner(
        "YOU MIGHT NEED TO ADD A DNS TXT RECORD FOR {}".format(domain),
        txt_f.path
    )

    contents = txt_f.contents()
    m = re.match("^(\S+)", contents)
    echo.h2("NAME")
    echo.indent(m.group(1), "    ")
    echo.hr()
    mv = re.search("v=\S+", contents)
    mk = re.search("k=\S+", contents)
    mp = re.search("p=[^\"]+", contents)
    echo.h2("VALUE")
    echo.indent("{} {} {}".format(mv.group(0), mk.group(0), mp.group(0)), "    ")

    echo.br()
    echo.bar("*")


# TODO -- add-email endpoint that will add a specific email address of the domain

def add_postfix_domains(domain, proxy_domains, proxy_email):

    if not proxy_domains:
        if not domain and not proxy_email:
            raise ValueError("Either pass in proxy_domains or (domain and proxy_emails)")

    # create directory /etc/postfix/virtual
    virtual_d = Dirpath("/etc/postfix/virtual")
    virtual_d.create()

    # create addresses directory
    addresses_d = Dirpath(virtual_d, "addresses")
    addresses_d.create()

    domains_f = Filepath(virtual_d, "domains")
    domains_f.create()
    old_domains = set(domains_f.lines())
    new_domains = set()
    domain_addresses = []

    if proxy_email:
        echo.h3("Adding catchall for {} routing to {}", domain, proxy_email)
        domain_f = Filepath(addresses_d, domain)
        domain_c = SpaceConfig(dest_path=domain_f.path)
        domain_c["@{}".format(domain)] = proxy_email
        domain_c.save()
        new_domains.add(domain)

    if proxy_domains:
        echo.h3("Adding domain files found in directory {} to postfix", proxy_domains)
        domains_d = Dirpath(proxy_domains)
        for f in domains_d.files():
            domain = f.name
            domain = re.sub("\.txt$", "", domain, flags=re.I)
            echo.h3("Compiling proxy addresses from {}", domain)
            domain_f = Filepath(addresses_d, domain)
            f.copy(domain_f)
            new_domains.add(domain)

    domains_f.write("\n".join(old_domains.union(new_domains)))

    domain_hashes = []
    for domain in domains_f.lines():
        domain_f = Filepath(addresses_d, domain)
        domain_hashes.append("hash:{}".format(domain_f.path))

    # this is an additive editing of the conf file, so we use the active conf
    # as the prototype
    m = Main(prototype_path=Main.dest_path)
    m.update(
        ("virtual_alias_domains", domains_f.path),
        ("virtual_alias_maps", ",\n  ".join(domain_hashes))
    )
    m.save()

    for domain in new_domains:
        addresses_f = Filepath(addresses_d, domain)
        cli.run("postmap {}".format(addresses_f))


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


def console():
    """we wrap captain.exit() so we can check for root"""
    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run command with sudo")

    exit()

console()

