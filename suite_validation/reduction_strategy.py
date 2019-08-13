from typing import List
import copy
from enum import Enum
from enum import auto
from abc import ABCMeta, abstractmethod
from suite_validation import coverage as cov


class ReductionStrategyError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg


class ReductionOption(Enum):
    NONE = auto()
    NAIVE = auto()
    DIFF = auto()


class ReductionStrategy:
    """
    A class that implements ReductionStrategy needs to overwrite "execute" which returns a reduced list of test coverages
    by providing a list of individual test coverages and a certain coverage goal. The returned reduced list is a subset
    of the given list of individual test coverages.
    """

    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def execute(
        individual_coverages: List[cov.TestCoverage], goal
    ) -> List[cov.TestCoverage]:
        raise NotImplementedError


def build(strategy: str) -> ReductionStrategy:
    if strategy == ReductionOption.NONE.name:
        return NoReductionStrategy()
    if strategy == ReductionOption.NAIVE.name:
        return NaiveReductionStrategy()
    if strategy == ReductionOption.DIFF.name:
        return FurthestDiffReductionStrategy()
    raise ReductionStrategyError("Reduction strategy {} is unknown".format(strategy))


class NoReductionStrategy(ReductionStrategy):
    def execute(
        self, individual_coverages: List[cov.TestCoverage], goal
    ) -> List[cov.TestCoverage]:
        """
        If reduction is switched off, an empty list is returned.
        :param individual_coverages: a list of individual test coverages
        :param goal: the coverage goal
        :return: an empty list of test coverages
        """
        return []


class NaiveReductionStrategy(ReductionStrategy):
    def execute(
        self, individual_coverages: List[cov.TestCoverage], goal
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


class FurthestDiffReductionStrategy(ReductionStrategy):
    def execute(
        self, individual_coverages: List[cov.TestCoverage], goal
    ) -> List[cov.TestCoverage]:
        """
            Finds a list of reduced individual tests by computing a total test coverage that is as effective as
            the total test coverage from the param individual_coverages.
            :param individual_coverages: a list of individual test coverages
            :param goal: the coverage goal
            :return: a list of reduced individual test coverages
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
