<!--
This file is part of TestCov,
a robust test executor with reliable coverage measurement:
https://gitlab.com/sosy-lab/software/test-suite-validator/

SPDX-FileCopyrightText: 2019-2020 Dirk Beyer <https://www.sosy-lab.org>

SPDX-License-Identifier: Apache-2.0
-->

# TestCov

[![Apache 2.0 License](https://img.shields.io/badge/license-Apache--2-brightgreen.svg?style=flat)](https://www.apache.org/licenses/LICENSE-2.0)

TestCov is a robust test-suite executor for C programs.
It uses Linux containers and namespaces to ensure robust and repeatable execution and coverage measurement of test suites.

For coverage computation, TestCov uses [gcov](https://gcc.gnu.org/onlinedocs/gcc/Gcov.html)
and [lcov](https://github.com/linux-test-project/lcov).
For containerization, TestCov uses parts of [BenchExec](https://github.com/sosy-lab/benchexec/).

## Details

For test execution,
TestCov creates a test harness (in C) that reads test values from standard input.
TestCov compiles the original program with the test harness.
This allows TestCov to efficiently feed test inputs to the program under test.
Test inputs are read from a given test suite. Test suites must be specified in the
exchangable [test-format](https://gitlab.com/sosy-lab/software/test-format) and given as a single zip-file (e.g., `suite.zip`).
TestCov is agnostic about the directory structure in the test-suite zip:
It recursively searches the zip for xml files that describe individual test cases, identified through their root element.
That means, that TestCov sees both of the following as valid test suites:

```
suite-1.zip
|- metadata.xml
|- test1.xml
|- test2.xml
```

```
suite-2.zip
|- suite/
    |- metadata.xml
    |- tests/
        |- t1.xml
        |- t2.xml
```

Upon completion,
TestCov reports the test coverage achieved by the executed test suite
and whether a test covered a call to an error function (currently, `__VERIFIER_error`).
In addition, file `output/results.json` gives detailed information about each executed test
(runtime of that test, individual coverage achieved by that test, etc.)
and a reduced test suite is produced at `output/reduced-suite.zip`.

## Requirements

* Python >= 3.6
* gcc >= 8.0
* lcov >= 1.13

The following requirements are automatically installed by `pipenv` or `setup.py` upon installation,
but can also be installed manually (e.g., through `pip`):
* lxml >= 4.0
* numpy >= 1.15
* BenchExec >= 1.20
* pycparser >= 2.19

Older versions of GCC can be used, but may mistakenly mark the last else-branch of a program
as covered, even it if wasn't. We thus recommend to use gcc version 8.0 or later.

Optional, for plotting (if not available, run `testcov` with argument `--no-plots`):
* matplotlib >= 3.1.0

For development, we use the [`black`](https://github.com/python/black) formatter,
[`pylint`](https://www.pylint.org/)
and [`nosetest`](https://nose.readthedocs.io/en/latest/).

## Installation

To install, you can run `pip install .`
or `python3 setup.py install`.

You can also use [`pipenv`](https://github.com/pypa/pipenv).

## Usage

To run test-suite `suite.zip` on program `foo.c`, call:

```bash
testcov --test-suite suite.zip foo.c
```

Run `bin/testcov --help` to get additional information
about configuration parameters.

## Support

If you find something not working or know of some improvements,
we're always happy about new issues or pull requests!
