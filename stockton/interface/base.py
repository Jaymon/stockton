from ..path import Filepath, Dirpath

class Interface(object):
    def base_configs(self):
        return []

    def base_get(self, name, configs=None):
        if not configs:
            configs = self.base_configs()

        base_fs = []
        for f in configs:
            base_fs.append(Filepath("{}.{}.base".format(f.path, name)))

        return base_fs

    def base_create(self, name, configs=None):
        """create a snapshot of the relevant config files so we could restore if needed"""
        if not configs:
            configs = self.base_configs()

        base_fs = []
        for f in configs:
            if f.exists():
                base_f = f.backup(suffix=".{}.base".format(name), ignore_existing=False)
                base_fs.append(base_f)

        return base_fs

    def base_restore(self, name, configs=None):
        """restore a snapshot of the base"""
        if not configs:
            configs = self.base_configs()

        for f in configs:
            base_f = Filepath("{}.{}.base".format(f.path, name))
            if base_f.exists():
                base_f.copy(f)

    def base_clear(self, name=""):
        for f in self.base_configs():
            d = f.directory
            d.delete_files("{}.base$".format(name))

    def reset(self):
        """Set it back completely fresh, you should never use this unless you know
        what you're doing"""
        self.uninstall()
        self.install()

    def start(self):
        raise NotImplementedError()

    def restart(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def is_running(self):
        raise NotImplementedError()

    def install(self):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()

