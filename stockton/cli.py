import os
import sys
import subprocess
import re
import hashlib


from captain import echo


from .path import Filepath


def ip():
    external_ip = cached_run("wget -qO- http://ifconfig.me/ip", ttl=10800)
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
            if capture_output:
                output += line
            else:
                #sys.stdout.write(line)
                echo.verbose(line)

        process.wait()
        if process.returncode > 0:
            raise RuntimeError("{} returned {}".format(cmd, process.returncode))

    except subprocess.CalledProcessError as e:
        raise RuntimeError("{} returned {}".format(cmd, e.returncode))

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


def postfix_reload():
    try:
        run("postfix status")

    except RuntimeError:
        run("postfix start")

    finally:
        run("postfix reload")


def opendkim_reload():
    output = run("/etc/init.d/opendkim status", capture_output=True)
    if re.search("opendkim\s+is\s+running", output, flags=re.I):
        run("/etc/init.d/opendkim start")

    else:
        run("/etc/init.d/opendkim restart")


def srs_reload():
    output = run("status postsrsd", capture_output=True)
    if re.search("stop", output, flags=re.I):
        run("start postsrsd")

    else:
        run("restart postsrsd")


def running(name):
    run("pgrep -f {}".format(name))

