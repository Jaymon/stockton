import re
import subprocess


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
            "^{}\s+descriptive\s+text\s+\"([^\"]*)\"$".format(self.host),
            output,
            filter_regex
        )
        for m in records:
            ret.append({
                "hostname": self.host,
                "text": m[0],
            })

        return ret

    def ip(self):
        pass

    def query(self, record):
        output = subprocess.check_output([
            "host",
            "-t {}".format(record),
            self.host
        ])
        return output

#     def records(self, record):
#         output = self.query(record)
#         return filter(None, output.splitlines(False))

