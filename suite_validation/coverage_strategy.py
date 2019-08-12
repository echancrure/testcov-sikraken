from typing import List
import copy
from enum import Enum
from suite_validation import coverage as cov


class ReductionStrategyError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg


class ReductionStrategy(Enum):
    NONE = "NONE"
    NAIVE = "NAIVE"
    DIFF = "DIFF"


class ReductionContext:
    """
    Has a reduction strategy to create a reduced test suite.
    """

    def __init__(self, strategy):
        self.strategy = strategy

    def execute(self, individual_coverages: List[cov.TestCoverage], goal):
        return self.strategy(individual_coverages, goal)

    @staticmethod
    def build(strategy: str) -> "ReductionContext":
        if strategy == ReductionStrategy.NONE.value:
            return ReductionContext(NoReduction())
        if strategy == ReductionStrategy.NAIVE.value:
            return ReductionContext(NaiveReduction())
        if strategy == ReductionStrategy.DIFF.value:
            return ReductionContext(FurthestDiffReduction())
        raise ReductionStrategyError(
            "Reduction strategy {} is unknown".format(strategy)
        )


class NoReduction:
    def __call__(
        self, individual_coverages: List[cov.TestCoverage], goal
    ) -> List[cov.TestCoverage]:
        return []


class NaiveReduction:
    def __call__(
        self, individual_coverages: List[cov.TestCoverage], goal
    ) -> List[cov.TestCoverage]:
        """
        Finds a list of reduced individual test coverages. Processes the list in sequence. An
        individual test coverage is added to the reduced coverage list when it extends the total coverage
        from the current reduced coverage list.
        :param individual_coverages:
        :param goal:
        :return:
        """
        # copy the list but not the contained objects
        individual_coverages = individual_coverages[:]
        total_tc = individual_coverages[0]
        individual_coverages.remove(total_tc)
        reduced_coverages = [total_tc]
        # make a deep copy because coverage gets overwritten
        total_tc = copy.deepcopy(total_tc)
        for tc in individual_coverages:
            if total_tc.coverage_type(goal).is_coverage_extended(
                tc.coverage_type(goal)
            ):
                reduced_coverages.append(tc)
                total_tc = cov.TestCoverage.merge(total_tc, tc)
        return reduced_coverages


class FurthestDiffReduction:
    def __call__(
        self, individual_coverages: List[cov.TestCoverage], goal
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
        total_tc = max(
            individual_coverages, key=lambda tc: tc.coverage_type(goal).coverage_hit
        )
        individual_coverages.remove(total_tc)
        reduced_coverages = [total_tc]
        # Make a deep copy because total_coverage will be overwritten. Otherwise this would affect the orginal test coverage either.
        total_tc = copy.deepcopy(total_tc)
        program_lines = total_tc.coverage_type(goal).relevant_program_lines
        for pl in program_lines:
            if total_tc.coverage_type(goal).is_program_line_covered(pl):
                # Program line is already covered.
                continue
            # Get all test coverages that cover the program line
            next_coverages = [
                tc
                for tc in individual_coverages
                if total_tc.coverage_type(goal).is_coverage_for_program_line_extended(
                    tc.coverage_type(goal), pl
                )
            ]
            if next_coverages:
                # Filter the optimal test coverage and merge it with the current total test coverage
                optimal_next_tc = compute_test_coverage_with_highest_extension(
                    total_tc, next_coverages, goal
                )
                reduced_coverages.append(optimal_next_tc)
                individual_coverages.remove(optimal_next_tc)
                total_tc = cov.TestCoverage.merge(total_tc, optimal_next_tc)
                # Get all test coverages that are now fully covered and remove them
                covered_coverages = [
                    tc
                    for tc in individual_coverages
                    if total_tc.coverage_type(goal).covers(tc.coverage_type(goal))
                ]
                for covered_tc in covered_coverages:
                    individual_coverages.remove(covered_tc)
        return reduced_coverages


def compute_test_coverage_with_highest_extension(
    tc: cov.TestCoverage, coverages: List[cov.TestCoverage], goal
) -> cov.TestCoverage:
    highest_coverage_extension = -1
    optimal_test_coverage = None
    for tc_other in coverages:
        _, other_extends_self = tc.coverage_type(goal).compute_coverage_relation(
            tc_other.coverage_type(goal)
        )
        if other_extends_self > highest_coverage_extension:
            highest_coverage_extension = other_extends_self
            optimal_test_coverage = tc_other
    assert highest_coverage_extension <= 1.0
    return optimal_test_coverage
