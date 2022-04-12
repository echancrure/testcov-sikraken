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

## Requirements

* Python >= 3.6
* gcc >= 8.0
* lcov >= 1.13
* clang-tidy (sometimes separate, sometimes included in clang package)

The following requirements are automatically installed upon installation:
* lxml >= 4.0
* numpy >= 1.15
* BenchExec >= 1.20
* pycparser >= 2.19

For cross-compilation (e.g., measuring coverage on 32bit compiles on a 64bit machine),
TestCov also requires 'gcc-multilib'.

Older versions of GCC can be used, but may mistakenly mark the last else-branch of a program
as covered, even if it wasn't. We thus recommend to use gcc version 8.0 or later.

Optional, for plotting (if not available, run `testcov` with argument `--no-plots`):
* matplotlib >= 3.1.0

For development, we use the [`black`](https://github.com/python/black) formatter,
[`pylint`](https://www.pylint.org/)
and [`pytest`](https://docs.pytest.org/en/6.2.x/).


## Usage

To check that TestCov is working as expected, you can run from the [repository root][repo]:

```bash
testcov --no-isolation --test-suite "test/suites/suite-simple-if.zip" "test/test_simple-if.c"
```

[repo]: https://gitlab.com/sosy-lab/software/test-suite-validator/

This should output the following:
```
⏳ Executing tests 2/2
✔️  Done!

---Results---
Tests run: 2
Tests in suite: 2
Coverage: 100.0%
Number of goals: 2
Result: DONE
```

The output tells you:
- the number of test cases that were executed ("Tests run: 2")
- the number of test cases in the test suite ("Tests in suite: 2")
- the coverage achieved by these test executions ("Coverage: 100.0%")
- the number of test goals in the program ("Number of goals: 2")
- the result of TestCov (Result: DONE).

The above command-line uses parameter `--no-isolation` to turn off isolation of test execution.
We use this parameter to make sure that if the command fails it is some issue with your installation of TestCov,
and not some issue with BenchExec or your cgroups configuration.

If above command works, but the following command fails, it is very likely that your system is not configured
as [required by BenchExec](https://github.com/sosy-lab/benchexec/blob/master/doc/INSTALL.md).

```bash
bin/testcov --test-suite "test/suites/suite-simple-if.zip" "test/test_simple-if.c"
```

Run `bin/testcov --help` to get additional information
about configuration parameters.

## Details

**Test Execution.**
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

**Coverage.** By default, TestCov measures branch coverage.
The coverage goal to measure can be define with parameter `--goal FILE`.
Example coverage-goal definitions can be found in [contrib/goal_files](contrib/goal_files).

**Results.**
Upon completion,
TestCov reports the test coverage achieved by the executed test suite
and whether a test covered a call to an error function (currently, `__VERIFIER_error`).
In addition, file `output/results.json` gives detailed information about each executed test
(runtime of that test, individual coverage achieved by that test, etc.)
and a reduced test suite is produced at `output/reduced-suite.zip`.


## Support

If you find something not working or know of some improvements,
we're always happy about new issues or pull requests!
