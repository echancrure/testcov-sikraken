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

[Unreleased]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.4...main
[3.4]: https://gitlab.com/sosy-lab/software/test-suite-validator/-/compare/v3.3...v3.4
