<!--
This file is part of TestCov,
a robust test executor with reliable coverage measurement:
https://gitlab.com/sosy-lab/software/test-suite-validator/

SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>

SPDX-License-Identifier: Apache-2.0
-->

# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.9] - 2023-11-28

### Added

- Option `--format` creates a temporary copy of the input program and formats it with `clang format`.
  The internal program transformations of TestCov work best with the formatting style of `clang format`.
- TestCov now generates a temporary file ensuring the presence of EOF. 
  This is necessary to abort test-execution.

## [3.8] - 2023-03-05

### Changed

- Maintenance release (bug fixes, improved tests)

## [3.7] - 2022-04-12

### Changed

- Verbose logging only verbosely logs messages of TestCov, not of other subcomponents.
  Especially matplotlib debug messages are not displayed anymore when command-line flag
  '--verbose' is used. This reduces clutter in the verbose output.
- The log prefix 'DEBUG:root' changed to 'DEBUG:suite_validation'.
- Nicer-looking progress display: Log messages and the progress display
  now work nicely together and do not intermingle, and the progress display shows
  the currently executed and total number of tests.

  Example: "⏳ Executing tests  20/227"


## [3.6] - 2021-12-16

### Added

- Report total number of tests found in a given test suite.
  We previously only reported the number of executed tests, but it may be interesting
  to see whether all identified tests were executed.

### Fixed

- A keyboard interrupt (SIGINT, usually Ctrl+C) does not display an exception anymore,
  but gracefully terminates.
  On an interrupt during test-suite execution, execution will stop
  and result files will be produced.
  It is then possible to abort the generation of result files by interrupting again.
- Get correct coverage measurement for single-line functions that call __assert_fail.
  A gcov_dump to dump recorded coverage was missing for these cases.


## [3.5] - 2021-11-03

### Changed

- Improved speed and supported language features for test-goal instrumentation in TestCov.
  We've replaced the Python-based implementation of adding test goals to the program
  with an implementation based on clang libtooling.
  This allows us to support the full range of C language features and GCC extensions.
  Before, we had to abort if unsupported features were used; most notably variadic arguments,
  but also GCC extensions that we did not remove explicitly.

### Fixed

- Removed a bug that made TestCov fail if preprocessed programs
  contained method declarations of builtin methods with the
  Star operator '*' right before the method name (e.g., '*malloc').
  Such preprocessed programs are now fully supported.

## [3.4] - 2021-10-16

### Added

- Always add calls to __gcov_flush before abort and __assert_fail calls.
  Before, this only happened for coverage goals "branch coverage" and "function-call coverage".
  This means that coverage measurements were not stored
  for condition and line coverage if an assert or abort was hit.
- TestCov and its dependencies can now be installed with `pip install .`

### Changed

- Changed __gcov_dump to __gcov_flush (__gcov_dump does not exist anymore in GCC 11).
- Support new naming scheme and directories for GCDA and GCOV files starting with GCC 11.
- During code transformation, TestCov now always removes preprocessor comments so that
  the original file name is not used in GCOV output (starting with GCC 11), but the name of the transformed file.
  This avoids user confusion in the output.
- Removed unnecessary semicolons after compiler directives in test harness.
- Improved error messages for missing files and on gcov and lcov errors.
- Cosmetic change: Call gcc with `--coverage` instead of `-fprofile-arcs -ftest-coverage`.
- For testing, switched from nosetest to pytest
- Store all metadata in setup.cfg instead of setup.py.
  (easier to read and can contain more information about other tools)
- Minor code improvements

[Unreleased]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.9...main
[3.9]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.8...v3.9
[3.8]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.7...v3.8
[3.7]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.6...v3.7
[3.6]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.5...v3.6
[3.5]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.4...v3.5
[3.4]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.3...v3.4
