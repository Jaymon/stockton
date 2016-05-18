import os
import sys
import subprocess
import re
import hashlib

from captain import echo

from .path import Filepath


class RunError(RuntimeError):
    # http://tldp.org/LDP/abs/html/exitcodes.html
    def __init__(self, cmd, code, output, e=None):
        self.cmd = cmd
        self.code = code
        self.output = output
        self.e = e
        message = "{} returned {} with output {}".format(
            cmd,
            code,
            output
        )
        super(RunError, self).__init__(message)

    def is_missing(self):
        return self.code == 127

    def is_general(self):
        return self.code == 1

    def is_misuse(self):
        return self.code == 2

    def is_permissions(self):
        return self.code == 126

    def is_bad_arg(self):
        return self.code == 128

    def is_terminated(self):
        return self.code == 130

    def search(self, regex):
        ret = False
        if re.search(regex, str(self), re.I):
            ret = True
        return ret


def ip():
    #external_ip = cached_run("wget -qO- http://ifconfig.me/ip", ttl=10800)
    external_ip = cached_run("wget -qO- http://icanhazip.com", ttl=10800)
    external_ip = external_ip.strip()
    m = re.match("^(?:\d+\.){3}\d+$", external_ip)
    return external_ip if m else ""


def cached_run(cmd, ttl=3600, **process_kwargs):
    # http://stackoverflow.com/questions/5297448/how-to-get-md5-sum-of-a-string
    cmd_h = hashlib.md5(cmd).hexdigest()
    cmd_h = "{}-{}".format(os.environ["USER"], cmd_h)
    f = Filepath.get_temp(cmd_h)
    if f.modified_within(seconds=ttl):
        output = f.contents()

    else:
        process_kwargs["capture_output"] = True
        output = run(cmd, **process_kwargs)
        f.write(output)

    return output


def run(cmd, capture_output=False, **process_kwargs):
    # we will allow overriding of these values
    echo.out("< {}", cmd)

    output = ""
    process_kwargs.setdefault("stderr", subprocess.STDOUT)

    # we will not allow these to be overridden via kwargs
    process_kwargs["shell"] = True
    process_kwargs["stdout"] = subprocess.PIPE
    #process_kwargs["cwd"] = self.cwd

    try:
        process = subprocess.Popen(
            cmd,
            **process_kwargs
        )

        for line in iter(process.stdout.readline, ""):
            output += line
            echo.verbose(line)

        line = process.stdout.read()
        process.wait()
        if process.returncode > 0:
            raise RunError(cmd, process.returncode, output)

    except subprocess.CalledProcessError as e:
        raise RunError(cmd, e.returncode, e.output, e)

    return output


def package(*packages, **kwargs):

    # http://serverfault.com/questions/143968/automate-the-installation-of-postfix-on-ubuntu
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    for p in packages:
        if kwargs.get("only_upgrade", False):
            run("apt-get -y install --only-upgrade {}".format(p))

        else:
            run("apt-get -y install --no-install-recommends {}".format(p))


def purge(*packages):

    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    for p in packages:
        #run("apt-get purge -y {}".format(p))
        run("apt-get -y remove --purge --auto-remove {}".format(p))

