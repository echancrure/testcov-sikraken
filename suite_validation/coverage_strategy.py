from typing import List
import copy
from suite_validation import coverage as cov


def compute_test_coverage_with_highest_extension(
    test_coverage: cov.TestCoverage, test_coverages: List[cov.TestCoverage], goal
) -> cov.TestCoverage:
    highest_coverage_extension = -1
    optimal_test_coverage = None
    for tc_other in test_coverages:
        _, other_extends_self = test_coverage.get_coverage_type_for_goal(
            goal
        ).compute_coverage_relation(tc_other.get_coverage_type_for_goal(goal))
        if other_extends_self > highest_coverage_extension:
            highest_coverage_extension = other_extends_self
            optimal_test_coverage = tc_other
    assert highest_coverage_extension <= 1.0
    return optimal_test_coverage


def find_efficient_tests(
    test_coverages: List[cov.TestCoverage], goal
) -> List[cov.TestCoverage]:
    total_test_coverage = max(
        test_coverages,
        key=lambda test_coverage: test_coverage.get_coverage_type_for_goal(
            goal
        ).total_summed_coverage(),
    )
    efficient_test_coverages = [copy.deepcopy(total_test_coverage)]
    test_coverages.remove(total_test_coverage)
    program_lines = total_test_coverage.get_coverage_type_for_goal(
        goal
    ).relevant_program_lines()
    for program_line in program_lines:
        if total_test_coverage.get_coverage_type_for_goal(goal).is_program_line_covered(
            program_line
        ):
            continue
        test_coverages_for_program_line = [
            tc
            for tc in test_coverages
            if total_test_coverage.get_coverage_type_for_goal(
                goal
            ).is_coverage_for_program_line_extended(
                tc.get_coverage_type_for_goal(goal), program_line
            )
        ]
        if test_coverages_for_program_line:
            optimal_next_test_coverage = compute_test_coverage_with_highest_extension(
                total_test_coverage, test_coverages_for_program_line, goal
            )
            efficient_test_coverages.append(optimal_next_test_coverage)
            test_coverages.remove(optimal_next_test_coverage)
            total_test_coverage = cov.TestCoverage.merge(
                total_test_coverage, optimal_next_test_coverage
            )
            covered_test_coverages = [
                tc
                for tc in test_coverages
                if total_test_coverage.get_coverage_type_for_goal(goal).covers(
                    tc.get_coverage_type_for_goal(goal)
                )
            ]
            for covered_test_coverage in covered_test_coverages:
                test_coverages.remove(covered_test_coverage)
    return efficient_test_coverages
