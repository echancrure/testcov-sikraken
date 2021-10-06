# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import suite_validation.coverage as cov


# pylint: disable=W0212
def _get_coverage(lines_hit):
    file_name = "dummy.c"
    test_vector_results = {}
    coverage = cov._LinesCoverage(lines_hit)

    return cov.TestCoverage(file_name, test_vector_results, coverage)


def test_coverage_equality():
    coverage1 = _get_coverage({0: 0})
    coverage2 = _get_coverage({0: 0})

    assert coverage1 == coverage2


def test_coverage_inequality_in_hits():
    coverage1 = _get_coverage({0: 0})
    coverage2 = _get_coverage({0: 1})

    assert coverage1 != coverage2


def test_coverage_inequality_in_lines():
    coverage1 = _get_coverage({0: 0})
    coverage2 = _get_coverage({1: 0})

    assert coverage1 != coverage2


def test_coverage_inequality_in_hits_and_lines():
    coverage1 = _get_coverage({0: 0})
    coverage2 = _get_coverage({1: 1})

    assert coverage1 != coverage2


def test_coverage_add_commutative():
    none_covered = _get_coverage({0: 0, 1: 0})
    all_covered = _get_coverage({0: 1, 1: 1})

    sum1 = none_covered + all_covered
    sum2 = all_covered + none_covered

    assert sum1 == sum2
