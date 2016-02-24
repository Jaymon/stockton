import os
from distutils import dir_util
import re
import subprocess


class Path(object):
    def __init__(self, *bits):
        self.path = ''
        if bits:
            bits = list(bits)
            bits[0] = self.normalize(bits[0])
            for i in range(1, len(bits)):
                bits[i] = bits[i].strip('\\/')
            self.path = os.path.join(*bits)

    @classmethod
    def normalize(cls, d):
        """completely normalize a relative path (a path with ../, ./, or ~/)"""
        return os.path.abspath(os.path.expanduser(str(d)))

    def __str__(self):
        return self.path

    def __unicode__(self):
        return unicode(self.__str__())

    def chmod(self, permissions):
        permissions = int(permissions)
        if permissions < 100 or permissions > 777:
            raise ValueError("permissions should be between 100 and 777")
        subprocess.check_call([
            "chmod",
            "{0:04}".format(permissions),
            self.path
        ])

    def chown(self, user):
        subprocess.check_call([
            "chown",
            user,
            self.path
        ])

    def chgrp(self, user):
        subprocess.check_call([
            "chgrp",
            user,
            self.path
        ])


class Dirpath(Path):
    def create(self):
        """create the directory path"""
        return dir_util.mkpath(self.path)

    def exists(self):
        return os.path.isdir(self.path)

    def files(self, regex=None):
        for root_dir, _, files in os.walk(self.path, topdown=True):
            for basename in files:
                if regex and not re.search(regex, basename, re.I):
                    continue

                yield Filepath(os.path.join(root_dir, basename))

            break


class Filepath(Path):
    @property
    def name(self):
        return os.path.basename(self.path)

    def __iter__(self):
        with open(self.path, "r") as f:
            for line in f:
                yield line

    def contents(self):
        with open(self.path, "r") as f:
            return f.read()

    def exists(self):
        return os.path.isfile(self.path)

    def copy(self, dest_path):
        """copy this file to dest_path"""
        dest_path = self.normalize(dest_path)
        if os.path.isdir(dest_path):
            basename = self.name
            dest_file = self.__class__(dest_path, basename)

        else:
            dest_file = self.__class__(dest_path)

        return shutil.copy(self.path, dest_file.path)

    def backup(self, suffix=".bak"):
        return self.copy("{}{}".format(self.path, suffix))
