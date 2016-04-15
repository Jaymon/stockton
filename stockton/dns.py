"""
DNS fun stuff

some relevant reading:
http://stackoverflow.com/questions/19322962/how-can-i-list-all-dns-records
"""
import re
import subprocess
import tempfile
import urllib
import gzip
import os

from .interface.dkim import DKIM
from . import cli


class Record(object):
    pass


class Mailserver(Record):

    def __init__(self, domain, ip):
        self.domain = Domain(str(domain))
        self.ip = Domain(ip)

    def needed_a(self):
        ret = []
        a = self.domain.a(self.ip.host)
        if not a:
            ret = [
                ("hostname", self.domain.host),
                ("target", self.ip.host),
            ]
        return ret

    def needed_ptr(self):
        ret = []
        ptr = self.ip.ptr(self.domain.host)
        if not ptr:
            ret = [
                ("hostname", self.domain.host),
            ]
        return ret


class Alias(Record):
    def __init__(self, domain, mailserver):
        self.domain = Domain(str(domain))
        self.mailserver = Domain(str(mailserver))

    def needed_mx(self):
        ret = []
        mx = self.domain.mx(self.mailserver.host)
        if not mx:
            ret = [
                ("hostname", self.domain.host),
                ("mailserver domain", self.mailserver.host),
                ("priority", "100"),
            ]
        return ret

    def needed_spf(self):
        ret = []
        txts = self.domain.spf()
        if not txts:
            ret = [
                ("hostname", self.domain.host),
                ("text", "v=spf1 mx ~all"),
            ]
        return ret

    def needed_dkim(self):
        ret = []
        dk = DKIM()
        domainkey = dk.domainkey(self.domain.host)
        d = Domain(domainkey.subdomain)
        txts = d.dkim()
        if not txts or (domainkey.p not in txts[0]["text"]):
            ret = [
                ("hostname", domainkey.subdomain),
                ("text", domainkey.text),
            ]
        return ret


class Domain(object):
    def __init__(self, host):
        self.host = host

    def records(self, regex, output, filter_regex=""):
        filter_regexp = re.compile(filter_regex, re.I) if filter_regex else None
        regexp = re.compile(regex, re.I)
        records = filter(None, output.splitlines(False))

        for record in records:
            check_record = record
            if filter_regexp:
                check_record = record if filter_regexp.search(record) else ""

            if check_record:
                m = regexp.search(check_record)
                if m:
                    yield m.groups()

    def nameservers(self, filter_regex=""):
        output = self.query("NS")
        records = [m[0] for m in self.records(
            "^{}\s+name\s+server\s+(.+?)\.?$".format(self.host),
            output,
            filter_regex
        )]
        return records

    def mx(self, filter_regex=""):
        ret = []
        output = self.query("mx")
        records = self.records(
            "^{}\s+mail\s+is\s+handled\s+by\s+(\d+)\s+(.+?)\.?$".format(self.host),
            output,
            filter_regex
        )
        for m in records:
            ret.append({
                "hostname": self.host,
                "priority": m[0],
                "target": m[1]
            })

        return ret

    def a(self, filter_regex=""):
        output = self.query("a")
        records = [m[0] for m in self.records(
            "^{}\s+has\s+address\s+((?:\d+\.){{3}}\d+)$".format(self.host),
            output,
            filter_regex
        )]
        return records

    def txt(self, filter_regex=""):
        ret = []
        output = self.query("txt")
        records = self.records(
            "^{}\s+descriptive\s+text\s+\"(.*?)\"$".format(self.host),
            output,
            filter_regex
        )
        for m in records:
            ret.append({
                "hostname": self.host,
                "text": m[0],
            })

        return ret

    def dkim(self):
        txts = self.txt("=dkim")
        if txts:
            for i in range(len(txts)):
                txts[i]["text"] = re.sub("\"\s+\"", "", txts[i]["text"])
                txts[i]["text"] = re.sub("\\\\;", ";", txts[i]["text"])
        return txts

    def spf(self):
        txts = self.txt("=spf")
        return txts

    def ptr(self, filter_regex=""):
        output = self.query("PTR")
        records = [m[0] for m in self.records(
            "^.*?\s+domain\s+name\s+pointer\s+(.+?)\.?$",
            output,
            filter_regex
        )]
        return records

    def rdns(self):
        ret = []
        ips = self.a()
        for ip in ips:
            d = type(self)(ip)
            for ptr in d.ptr():
                if self.host in ptr:
                    ret.append(ip)
        return ret

    def query(self, record):
        output = ""
        try:
            output = subprocess.check_output([
                "host",
                #"-t {}".format(record),
                "-t",
                record,
                self.host
            ])
        except subprocess.CalledProcessError:
            pass

        return output

#     def records(self, record):
#         output = self.query(record)
#         return filter(None, output.splitlines(False))

