import os
import sys
import subprocess
import re


def ask(question):
    if sys.version_info[0] > 2:
        answer = input("{}: ".format(question))
    else:
        answer = raw_input("{}: ".format(question))

    return answer


def ip():
    external_ip = run("wget -qO- http://ifconfig.me/ip", capture_output=True)
    return external_ip.strip()


def run(cmd, capture_output=False, **process_kwargs):
    # we will allow overriding of these values
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
                sys.stdout.write(line)

        process.wait()
        if process.returncode > 0:
            raise RuntimeError("{} returned {}".format(cmd, process.returncode))

    except subprocess.CalledProcessError as e:
        raise RuntimeError("{} returned {}".format(cmd, e.returncode))

    return output


def package(*packages, **kwargs):
    for p in packages:
        if kwargs.get("only_upgrade", False):
            run("apt-get -y install --only-upgrade {}".format(p))

        else:
            run("apt-get -y install --no-install-recommends {}".format(p))


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


def print_err(format_str, *args, **kwargs):
    if isinstance(format_str, basestring):
        sys.stderr.write(format_str.format(*args, **kwargs)) 
        sys.stderr.write(os.linesep)
        sys.stderr.flush()

    else:
        sys.stderr.write(str(format_str)) 
        sys.stderr.write(os.linesep)
        sys.stderr.flush()


def print_out(format_str, *args, **kwargs):
    if isinstance(format_str, basestring):
        sys.stdout.write(format_str.format(*args, **kwargs)) 
        sys.stdout.write(os.linesep)
        sys.stdout.flush()

    else:
        sys.stdout.write(str(format_str)) 
        sys.stdout.write(os.linesep)
        sys.stdout.flush()


