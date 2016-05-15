import os
from distutils import dir_util
import re
import subprocess
import shutil
import codecs
import datetime
import tempfile
from contextlib import contextmanager
import hashlib


class Path(object):
    @property
    def directory(self):
        return Dirpath(os.path.dirname(self.path))

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

    @classmethod
    def get_temp(cls, *bits):
        tmp = tempfile.gettempdir()
        return cls(tmp, *bits)

    @classmethod
    def create_temp(cls, *bits):
        instance = cls.get_temp(*bits)
        instance.create()
        return instance

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

    def move(self, path):
        p = type(self)(path)
        shutil.move(self.path, p.path)
        self.path = p.path

    def rename(self, name):
        p = type(self)(self.directory, name)
        return self.move(p)


class Dirpath(Path):
    def count(self, regex=None):
        count = 0
        regexp = re.compile(regex, re.I) if regex else None
        for root_dir, directories, files in os.walk(self.path):
            if regexp:
                count += len([f for f in files if regexp.search(f)])
                count += len([d for d in directories if regexp.search(d)])

            else:
                count += len(files) + len(directories)

        return count

    def __len__(self):
        return self.count()

    def create(self):
        """create the directory path"""
        return dir_util.mkpath(self.path)

    def exists(self):
        return os.path.isdir(self.path)

    def clear(self):
        """this will clear a directory path of all files and folders"""
        # http://stackoverflow.com/a/1073382/5006
        for root, dirs, files in os.walk(self.path, topdown=True):
            for td in dirs:
                shutil.rmtree(os.path.join(root, td))

            for tf in files:
                os.unlink(os.path.join(root, tf))

            break

    def delete(self):
        try:
            shutil.rmtree(self.path)

        except OSError:
            pass

    def files(self, regex=None):
        regexp = re.compile(regex, re.I) if regex else None
        for root_dir, _, files in os.walk(self.path, topdown=True):
            for basename in files:
                if regexp and not regexp.search(basename):
                    continue

                yield Filepath(os.path.join(root_dir, basename))

            break

    def delete_files(self, regex):
        """delete all files matching regex"""
        if not regex:
            raise ValueError("regex was empty")

        count = 0
        for f in self.files(regex):
            count += 1
            f.delete()

        return count

    def create_file(self, name, contents=""):
        """create the file with basename in this directory with contents"""
        output_file = Filepath(self.path, name)
        oldmask = os.umask(0)
        with output_file.open('w+') as f:
            f.truncate(0)
            f.seek(0)
            f.write(contents)
        oldmask = os.umask(oldmask)
        return output_file


class Filepath(Path):
    @property
    def checksum(self):
        """return -- string -- the md5 hash of the file"""
        h = hashlib.md5()
        # http://stackoverflow.com/a/21565932/5006
        blocksize = 204800
        with self.open() as fp:
            for block in iter(lambda: fp.read(blocksize), ""):
                h.update(block)
        return h.hexdigest()

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def modified(self):
        # http://stackoverflow.com/a/1526089/5006
        t = os.path.getmtime(self.path)
        return datetime.datetime.fromtimestamp(t)

    def __iter__(self):
        with open(self.path, "r") as f:
            for line in f:
                yield line

    def contents(self):
        with open(self.path, "r") as f:
            return f.read()

    def lines(self):
        """this is different than python built-in lines() method in that it strips
        the line endings from the end of the string"""
        with open(self.path, "r") as f:
            for line in f:
                yield line.rstrip()

    def lc(self):
        """return line count"""
        return len(list(self.lines()))

    def exists(self):
        return os.path.isfile(self.path)

    def clear(self):
        self.write("")

    def delete(self):
        try:
            os.unlink(self.path)

        except OSError:
            pass

    def copy(self, dest_path):
        """copy this file to dest_path"""
        dest_path = self.normalize(dest_path)
        if os.path.isdir(dest_path):
            basename = self.name
            dest_file = type(self)(dest_path, basename)

        else:
            dest_file = type(self)(dest_path)

        return shutil.copy(self.path, dest_file.path)

    def backup(self, suffix=".bak", ignore_existing=True):
        """backup the file to the same directory with given suffix

        suffix -- str -- what will be appended to the file name (eg, foo.ext becomes
            foo.ext.bak)
        ignore_existing -- boolean -- if True overright an existing backup, if false
            then don't backup if a backup file already exists
        return -- instance -- an instance of Filepath with the backup filepath
        """
        path = "{}{}".format(self.path, suffix)
        bak = type(self)(path)
        if ignore_existing or not bak.exists():
            self.copy(path)
        return bak

    def append(self, contents):
        with self.open("a") as f:
        #with codecs.open(self.path, encoding='utf-8', mode='a') as f:
            ret = f.write(contents)

        return ret

    def open(self, mode="r"):
        return codecs.open(self.path, encoding='utf-8', mode=mode)

    def write(self, contents, mode="w+"):
        with self.open(mode) as f:
        #with codecs.open(self.path, encoding='utf-8', mode='w+') as f:
            #f.truncate(0)
            #f.seek(0)
            ret = f.write(contents)

        return ret

    def writelines(self, lines, mode="w+"):
        """this is different than built-in python writelines in that it adds the
        newlines at the end of each line"""
        with self.open(mode) as f:
            ret = f.writelines(("{}\n".format(line) for line in lines))

        return ret

    def create(self):
        """create the file if it doesn't exist, touch the file if it does"""
        # http://stackoverflow.com/a/1160227/5006

        with open(self.path, 'a') as f:
            os.utime(self.path, None)

        return

        #with open(self.path, 'a') as f:
        with open(self.path, 'w+') as f:
            os.utime(self.path, None)
#             f.flush()
#             os.fsync(f.fileno())

    def contains(self, regex, flags=0):
        flags |= re.M
        m = None
        try:
            m = re.search(regex, self.contents(), flags=flags)

        except IOError:
            # TODO -- check for file not existing EOINT or whatever and only
            # suppress that
            # raised when file doesn't exist
            pass
        return True if m else False

    def delete_lines(self, regex, flags=0):
        """returns how many lines were removed"""
        count = 0
        regexp = re.compile(regex, flags)
        with self.open("r") as f:
            lines = f.readlines()

        with self.open("w") as f:
            f.truncate(0)
            for line in lines:
                if regexp.search(line):
                    count += 1
                else:
                    f.write(line)

        return count

    def modified_within(self, seconds=0, **timedelta_kwargs):
        """returns true if the file has been modified within the last seconds

        seconds -- integer -- how many seconds
        **timedelta_kwargs -- dict -- can be thing like days, must be passed in
            named
        return -- boolean -- True if file has been modified after the seconds back
        """
        if not self.exists(): return False

        now = datetime.datetime.now()
        then = self.modified
        timedelta_kwargs["seconds"] = seconds
        td_check = datetime.timedelta(**timedelta_kwargs)
        #pout.v(now, td_check, then, (now - td_check))
        return (now - td_check) < then


class Sentinal(object):
    def __init__(self, name):
        self.name = name
        now = datetime.datetime.utcnow()
        self.year = now.strftime("%Y")
        self.month = now.strftime("%m")
        self.f = Filepath.get_temp("{}-{}-{}".format(self.name, self.year, self.month))

    def exists(self):
        ret = False
        try:
            ret = self._exists

        except AttributeError:
            ret = self.f.exists()

        finally:
            self._exists = ret

        return ret

    def create(self):
        self.f.create()
        self._exists = True

    @classmethod
    @contextmanager
    def check(cls, name):
        """yields a boolean, execute to check if the block whould be run"""
        instance = cls(name)
        exists = instance.exists()
        yield instance
        if not exists:
            instance.create()

    def __str__(self):
        return self.f.path

    def __nonzero__(self):
        return self.exists()

