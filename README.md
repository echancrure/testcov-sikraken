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

## Support

If you find something not working or know of some improvements,
we're always happy about new issues or pull requests!
