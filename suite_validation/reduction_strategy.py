# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020 Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module with test-suite reduction strategies."""

from typing import List
import copy
from suite_validation import _logger as logging
from suite_validation import coverage as cov

NO_REDUCTION = "NONE"
BYORDER_REDUCTION = "BY_ORDER"
FURTHEST_DIFF_REDUCTION = "DIFF"


class ReductionStrategyError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg


def no_reduction(
    individual_coverages: List[cov.TestCoverage],
) -> List[cov.TestCoverage]:
    """
    If reduction is switched off, an empty list is returned.
    :param individual_coverages: a list of individual test coverages
    :return: an empty list of test coverages
    """
    del individual_coverages
    return []


def naive_reduction(
    individual_coverages: List[cov.TestCoverage],
) -> List[cov.TestCoverage]:
    """
    Finds a list of reduced individual test coverages. Processes the list in sequence. An
    individual test coverage is added to the reduced coverage list when it extends the total coverage
    from the current reduced coverage list.
    :param individual_coverages: a list of individual test coverages
    :param goal: the coverage goal
    :return: a list of reduced individual test coverages
    """
    # copy the list but not the contained objects
    individual_coverages = individual_coverages[:]
    reduced_coverages = []
    total_tc = None
    # make a deep copy because coverage gets overwritten
    for tc in individual_coverages:
        assert not total_tc or total_tc.coverage
        if not tc.coverage or tc.coverage == 0:
            continue
        if not total_tc or total_tc.coverage.is_coverage_extended(tc.coverage):
            logging.debug("Adding %s to reduced coverages", tc)
            assert tc.coverage > 0
            reduced_coverages.append(tc)
            if not total_tc:
                total_tc = tc
            else:
                total_tc = total_tc + tc
    return reduced_coverages


def furthest_diff_reduction(
    individual_coverages: List[cov.TestCoverage],
) -> List[cov.TestCoverage]:
    """
    Finds a list of reduced individual tests by computing a total test coverage that is as effective as
    the total test coverage from the param individual_coverages.
    :param individual_coverages: a list of individual test coverages
    :return: a list of reduced individual test coverages
    """
    individual_coverages = individual_coverages[:]
    assert all(c.coverage for c in individual_coverages)
    # From the whole individual test set get the most optimal one and let total_coverage be assigned with the result
    total_tc = max(individual_coverages, key=lambda tc: tc.hits)
    individual_coverages.remove(total_tc)
    reduced_coverages = [total_tc]
    # Make a deep copy because total_coverage will be overwritten. Otherwise this would affect the orginal test coverage either.
    total_tc = copy.deepcopy(total_tc)
    program_lines = total_tc.coverage.relevant_program_lines
    for pl in program_lines:
        assert total_tc.coverage
        if total_tc.coverage.is_program_line_covered(pl):
            # Program line is already covered.
            continue
        # Get all test coverages that cover the program line
        next_coverages = [
            tc
            for tc in individual_coverages
            if tc.coverage
            and total_tc.coverage.is_coverage_for_program_line_extended(tc.coverage, pl)
        ]
        if next_coverages:
            # Filter the optimal test coverage and merge it with the current total test coverage
            optimal_next_tc = compute_test_coverage_with_highest_extension(
                total_tc, next_coverages
            )
            reduced_coverages.append(optimal_next_tc)
            individual_coverages.remove(optimal_next_tc)
            total_tc = total_tc + optimal_next_tc
            # Get all test coverages that are now fully covered and remove them
            covered_coverages = [
                tc
                for tc in individual_coverages
                if tc.coverage and total_tc.coverage.covers(tc.coverage)
            ]
            for covered_tc in covered_coverages:
                individual_coverages.remove(covered_tc)
    return reduced_coverages


REDUCTION_STRATEGIES = {
    NO_REDUCTION: no_reduction,
    BYORDER_REDUCTION: naive_reduction,
    FURTHEST_DIFF_REDUCTION: furthest_diff_reduction,
}


def execute(
    strategy: str, individual_coverages: List[cov.TestCoverage]
) -> List[cov.TestCoverage]:
    if not individual_coverages:
        return []
    if strategy in REDUCTION_STRATEGIES:
        return REDUCTION_STRATEGIES[strategy](individual_coverages)
    raise ReductionStrategyError(f"Reduction strategy {strategy} is unknown")


def compute_test_coverage_with_highest_extension(
    tc: cov.TestCoverage, coverages: List[cov.TestCoverage]
) -> cov.TestCoverage:
    highest_coverage_extension: float = -1
    optimal_test_coverage = None
    for tc_other in coverages:
        assert tc.coverage and tc_other.coverage
        _, other_extends_self = tc.coverage.compute_coverage_relation(tc_other.coverage)
        if other_extends_self > highest_coverage_extension:
            highest_coverage_extension = other_extends_self
            optimal_test_coverage = tc_other
    assert highest_coverage_extension <= 1.0
    assert optimal_test_coverage is not None
    return optimal_test_coverage
