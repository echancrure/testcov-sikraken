#!/usr/bin/env python3

import re
from setuptools import setup

with open('suite_validation/__init__.py') as inp:
    VERSION = re.search(r'^__VERSION__\s*=\s*[\"\'](.*)[\"\']', inp.read(),
                        re.M).group(1)

setup(
    name='tbf-testsuite-validator',
    version=VERSION,
    author='Dirk Beyer',
    description='A container-based test-suite executor',
    url='https://gitlab.com/sosy-lab/software/testsuite-validator',
    packages=['suite_validation'],
    scripts=['bin/tbf-testsuite-validator'],
    install_requires=[
        'lxml>=4.0.0',
    ],
    setup_requires=[
        'nose>=1.0',
    ],
    tests_require=[
        'nose>=1.0',
    ],
    test_suite='nose.collector',
    license='multiple',
    keywords='test suite test-case generation verification',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'Operation System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Testing',
    ],
    platforms=['Linux'],
)
