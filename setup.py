#!/usr/bin/env python
# http://docs.python.org/distutils/setupscript.html
# http://docs.python.org/2/distutils/examples.html

from setuptools import setup, find_packages
import re
import os


name = "stockton"
with open(os.path.join(name, "__init__.py")) as f:
    version = re.search("^__version__\s*=\s*[\'\"]([^\'\"]+)", f.read(), flags=re.I | re.M).group(1)

setup(
    name=name,
    version=version,
    description='Easy peasy email forwarding for a custom domain',
    author='Jay Marcyes',
    author_email='jay@marcyes.com',
    url='http://github.com/jaymon/{}'.format(name),
    packages=find_packages(),
    license='GPLv2+',
    install_requires=['geoip2', 'captain'],
    tests_require=['testdata'],
    classifiers=[ # https://pypi.python.org/pypi?:action=list_classifiers
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Communications :: Email',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)'
    ],
    entry_points = {
        'console_scripts': [
            '{} = {}.__main__:console'.format(name, name),
        ],
    },
)
