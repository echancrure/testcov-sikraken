from typing import List
import copy
from suite_validation import coverage as cov


def compute_test_coverage_with_highest_extension(
    test_coverage: cov.TestCoverage, test_coverages: List[cov.TestCoverage], goal
) -> cov.TestCoverage:
    highest_coverage_extension = -1
    optimal_test_coverage = None
    for tc_other in test_coverages:
        _, other_extends_self = test_coverage.coverage_type(
            goal
        ).compute_coverage_relation(tc_other.coverage_type(goal))
        if other_extends_self > highest_coverage_extension:
            highest_coverage_extension = other_extends_self
            optimal_test_coverage = tc_other
    assert highest_coverage_extension <= 1.0
    return optimal_test_coverage


def find_reduced_test_suite(
    individual_coverages: List[cov.TestCoverage], goal
) -> List[cov.TestCoverage]:
    """
    Finds a list of reduced individual tests by computing a total test coverage that is as effective as
    the total test coverage from the param individual_coverages.
    :param individual_coverages: a list of individual test coverages
    :param goal: the coverage goal
    :return: a set of individual test coverages that is a subset of the param individual_coverages
    """
    individual_coverages = individual_coverages[:]
    # From the whole individual test set get the most optimal one and let total_coverage be assigned with the result
    total_coverage = max(
        individual_coverages, key=lambda tc: tc.coverage_type(goal).coverage_hit
    )
    individual_coverages.remove(total_coverage)
    reduced_test_coverages = [total_coverage]
    # Make a deep copy because total_coverage will be overwritten. Otherwise this would affect the orginal test coverage either.
    total_coverage = copy.deepcopy(total_coverage)
    program_lines = total_coverage.coverage_type(goal).relevant_program_lines
    for line in program_lines:
        if total_coverage.coverage_type(goal).is_program_line_covered(line):
            # Program line is already covered.
            continue
        # Get all test coverages that cover the program line
        next_coverages = [
            tc
            for tc in individual_coverages
            if total_coverage.coverage_type(goal).is_coverage_for_program_line_extended(
                tc.coverage_type(goal), line
            )
        ]
        if next_coverages:
            # Filter the optimal test coverage and merge it with the current total test coverage
            optimal_next_coverage = compute_test_coverage_with_highest_extension(
                total_coverage, next_coverages, goal
            )
            reduced_test_coverages.append(optimal_next_coverage)
            individual_coverages.remove(optimal_next_coverage)
            total_coverage = cov.TestCoverage.merge(
                total_coverage, optimal_next_coverage
            )
            # Get all test coverages that are now fully covered and remove them
            covered_coverages = [
                tc
                for tc in individual_coverages
                if total_coverage.coverage_type(goal).covers(tc.coverage_type(goal))
            ]
            for covered_test_coverage in covered_coverages:
                individual_coverages.remove(covered_test_coverage)
    return reduced_test_coverages
