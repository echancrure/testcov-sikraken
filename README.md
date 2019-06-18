# Testsuite Validator

The tool `bin/tbf-testsuite-validator` creates a C harness
that reads test values from standard input,
compiles the original program file against this harness
and uses it to execute a test suite specified in the test-format.
Upon completion,
it will report the test coverage achieved by the executed test suite
and whether a test covered a call to `__VERIFIER_error()`.
If the latter is the case, it also creates a directory `test-suite`
that contains a covering test and a corresponding executable harness.

Run `bin/tbf-testsuite-validator --help` to get additional information
about its usage.

## Requirements

* Python >= 3.5
* clang and llvm >= 3.9

The following requirements are automatically installed by `pipenv` or `setup.py` upon installation,
but can also be installed manually (e.g., through `pip`):
* lxml >= 4.0
* BenchExec >= 1.20

For development, we use the [`black`](https://github.com/python/black) formatter,
[`pylint`](https://www.pylint.org/)
and [`nosetest`](https://nose.readthedocs.io/en/latest/).

You can use [`pipenv`](https://github.com/pypa/pipenv)
to install dependencies automatically.


## Support

If you find something not working or know of some improvements,
we're always happy about new issues or pull requests!
