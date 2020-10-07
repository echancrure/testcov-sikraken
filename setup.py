#!/usr/bin/env python3

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import re
from setuptools import setup

with open('suite_validation/_tool_info.py') as inp:
    VERSION = re.search(r'^__VERSION__\s*=\s*[\"\'](.*)[\"\']', inp.read(),
                        re.M).group(1)

setup(
    name='testcov',
    version=VERSION,
    author='Dirk Beyer',
    description='A container-based test-suite executor with coverage measurement',
    url='https://gitlab.com/sosy-lab/software/test-suite-validator',
    packages=['suite_validation'],
    scripts=['bin/testcov'],
    install_requires=[
        'lxml>=4.0.0',
        'benchexec>=1.20',
        'pycparser>=2.19',
        'numpy>=1.15',
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
