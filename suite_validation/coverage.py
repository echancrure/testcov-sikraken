# testsuite-validator is tool for validation and execution of test suites.
# This file is part of testsuite-validator.
#
# Copyright (C) 2018  Dirk Beyer
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module for coverage of individual tests"""

from enum import Enum
import os
import logging
import csv

from typing import Dict, Tuple, List, Optional
from abc import ABCMeta, abstractmethod
from suite_validation import execution_utils as eu

# Constants for csv output
FILE_NAME_INDIVIDUAL_TEST_COVERAGES = "individual-test-coverages.csv"
FILE_NAME_REDUCED_TEST_COVERAGES = "reduced-test-coverages.csv"
LINES_COVERED = "Line Coverage"
BRANCHES_COVERED = "Branch Coverage"
CONDITIONS_COVERED = "Condition Coverage"
TEST = "Test"
HEADER = [TEST, LINES_COVERED, BRANCHES_COVERED, CONDITIONS_COVERED]
DELIMITER_TEST_COVERAGES = "\t"

MODULE_DIRECTORY = os.path.join(os.path.dirname(__file__), os.path.pardir)

LLVM_GCOV_BINARY = os.path.join(MODULE_DIRECTORY, "bin/llvm-gcov")

TRACE_FILE_CONDITION_NOT_VISITED = "-"


class CoverageCreationError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg


class LcovPrefix(Enum):
    FILEPATH = "SF:"
    BRANCH_LINE_CONDITION_HIT_COUNTER = "BRDA:"
    CONDITIONS_FOUND = "BRF:"
    CONDITIONS_TAKEN = "BRH:"
    LINE_HIT_COUNTER = "DA:"
    LINES_NONZERO_HIT_COUNTER = "LH:"
    LINES_FOUND = "LF:"
    END_OF_RECORD = "end_of_record"


class LcovSector(Enum):
    BEFORE_TEST_RECORD = 0
    IN_TEST_RECORD = 1


class CoverageComparable:
    """
    A class that implements CoverageComparable must be able to compute the coverage relation between an object of the
    class and another object of the same class. The computation of a coverage relation must return two values: The first
    value represents the ratio of the measured unit (for instance line coverage) that the class object covers but that
    is not covered by the other object. The second value represents the ratio of the measured unit that the other object
    covers but is not covered by the class object.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def compute_coverage_relation(
        self, other: "CoverageComparable"
    ) -> Tuple[float, float]:
        """
        Computes the coverage relation to another instance that implements CoverageComparable.
        The returned tuple contains two values in interval [0,1].
        :param other:
        :return: Tuple(covered_only_by_self, covered_only_by_other)
        """
        raise NotImplementedError

    @abstractmethod
    def is_coverage_for_program_line_extended(
        self, other: "CoverageComparable", pl
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_program_line_covered(self, pl) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def relevant_program_lines(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def coverage_hit(self) -> int:
        raise NotImplementedError

    def covers(self, other: "CoverageComparable") -> bool:
        only_covered_by_self, only_covered_by_other = self.compute_coverage_relation(
            other
        )
        return only_covered_by_other <= 0 < only_covered_by_self

    def is_covered(self, other: "CoverageComparable") -> bool:
        only_covered_by_self, only_covered_by_other = self.compute_coverage_relation(
            other
        )
        return only_covered_by_self <= 0 < only_covered_by_other

    def is_coverage_extended(self, other: "CoverageComparable") -> bool:
        _, only_covered_by_other = self.compute_coverage_relation(other)
        return only_covered_by_other > 0


class ConditionsEntry:
    """
    An instance of ConditionsEntry has a dictionary with indices as keys to address the conditions and counter numbers
    as corresponding values which say how often the conditions have been hit. Moreover an instance has a program line
    to relate to the program where the conditions appear. Note that ConditionsEntry does not implement
    CoverageComparable.
    An instance of ConditionsEntry is fully covered when each indices has a corresponding counter value that is greater
    than zero.
    """

    def __init__(self, program_line: int, conditions_hit_counter: Dict[int, int]):
        self.program_line = program_line
        self.conditions_hit_counter = conditions_hit_counter

    @property
    def conditions_total(self) -> int:
        return len(self.conditions_hit_counter)

    @property
    def conditions_hit(self) -> int:
        return len([v for v in self.conditions_hit_counter.values() if v > 0])

    @property
    def conditions_indices(self):
        return self.conditions_hit_counter.keys()

    @property
    def is_program_line_covered(self) -> bool:
        return all(c > 0 for c in self.conditions_hit_counter.values())

    @property
    def relevant_program_lines(self):
        return [self.program_line]

    @staticmethod
    def merge(
        entry1: "ConditionsEntry", entry2: "ConditionsEntry"
    ) -> "ConditionsEntry":
        assert entry1.program_line == entry2.program_line
        summarized_conditions_hit_counter = {}
        for condition_index in entry1.conditions_hit_counter:
            summarized_conditions_hit_counter[condition_index] = (
                entry1.conditions_hit_counter[condition_index]
                + entry2.conditions_hit_counter[condition_index]
            )
        return ConditionsEntry(entry1.program_line, summarized_conditions_hit_counter)

    def same_program_line(self, other: "ConditionsEntry") -> bool:
        return self.program_line == other.program_line

    def set_condition_to_hit_counter(self, index: int, number_of_condition_taken: int):
        self.conditions_hit_counter[index] = number_of_condition_taken

    def compute_coverage_relation(self, other: "ConditionsEntry") -> Tuple[int, int]:
        assert self.program_line == other.program_line
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        for key in self.conditions_indices:
            if (
                self.conditions_hit_counter[key]
                <= 0
                < other.conditions_hit_counter[key]
            ):
                conditions_only_covered_by_other += 1
            if (
                other.conditions_hit_counter[key]
                <= 0
                < self.conditions_hit_counter[key]
            ):
                conditions_only_covered_by_self += 1
        return conditions_only_covered_by_self, conditions_only_covered_by_other

    def is_coverage_for_program_line_extended(self, other: "ConditionsEntry"):
        return any(
            hit_counter <= 0 < other.conditions_hit_counter[pl]
            for pl, hit_counter in self.conditions_hit_counter.items()
        )


class ConditionsCoverage(CoverageComparable):
    """
    Contains a list of ConditionsEntry to represent all ConditionEntries that appear in the program.
    Each ConditionsEntry is assigned to a certain program line. A conditions coverage satisfies full coverage
    when each ConditionsEntry satisfies full coverage.
    """

    def __init__(self, conditions_entries: List[ConditionsEntry]):
        self.conditions_entries = conditions_entries

    @property
    def conditions_hit(self) -> int:
        return sum(e.conditions_hit for e in self.conditions_entries)

    @property
    def conditions_total(self) -> int:
        number_of_conditions_found = 0
        for condition_entry in self.conditions_entries:
            number_of_conditions_found += condition_entry.conditions_total
        return number_of_conditions_found

    @property
    def relevant_program_lines(self):
        return [entry.program_line for entry in self.conditions_entries]

    @property
    def coverage_hit(self) -> int:
        return self.conditions_hit

    @staticmethod
    def merge(
        cov1: "ConditionsCoverage", cov2: "ConditionsCoverage"
    ) -> "ConditionsCoverage":
        merged = [
            ConditionsEntry.merge(e1, e2)
            for e1 in cov1.conditions_entries
            for e2 in cov2.conditions_entries
            if e1.same_program_line(e2)
        ]
        return ConditionsCoverage(merged)

    def get_conditions_entry(self, program_line) -> Optional[ConditionsEntry]:
        return next(
            iter(
                [e for e in self.conditions_entries if e.program_line == program_line]
            ),
            None,
        )

    def compute_coverage_relation(
        self, other: "ConditionsCoverage"
    ) -> Tuple[float, float]:
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        entries_per_line = (
            (e1, e2)
            for e1 in self.conditions_entries
            for e2 in other.conditions_entries
            if e1.same_program_line(e2)
        )
        for conditions_self, conditions_other in entries_per_line:
            current_only_self, current_only_other = conditions_self.compute_coverage_relation(
                conditions_other
            )
            conditions_only_covered_by_self += current_only_self
            conditions_only_covered_by_other += current_only_other
        if self.conditions_total == 0:
            return 0.0, 0.0
        return (
            float(conditions_only_covered_by_self) / float(self.conditions_total),
            float(conditions_only_covered_by_other) / float(self.conditions_total),
        )

    def is_program_line_covered(self, pl) -> bool:
        if pl not in self.relevant_program_lines:
            return False
        return self.get_conditions_entry(pl).is_program_line_covered

    def is_coverage_for_program_line_extended(
        self, other: "ConditionsCoverage", pl
    ) -> bool:
        return self.get_conditions_entry(pl).is_coverage_for_program_line_extended(
            other.get_conditions_entry(pl)
        )


class LinesCoverage(CoverageComparable):
    """
    Contains a dict with the program lines as keys and hit numbers as corresponding values. If each program line has
    a hit number greater than zero the program is fully covered regarding the line coverage.
    """

    def __init__(self, program_lines_hit_counter: Dict[int, int]):
        self.lines_hit_counter = program_lines_hit_counter

    @property
    def lines_hit(self) -> int:
        lines_taken = 0
        for program_line in self.relevant_program_lines:
            if self.lines_hit_counter[program_line] > 0:
                lines_taken += 1
        return lines_taken

    @property
    def lines_total(self) -> int:
        return len(self.relevant_program_lines)

    @property
    def relevant_program_lines(self):
        return self.lines_hit_counter.keys()

    @property
    def coverage_hit(self) -> int:
        return self.lines_hit

    @staticmethod
    def merge(cov1: "LinesCoverage", cov2: "LinesCoverage"):
        summarized_lines_coverage = {
            l: cov1.lines_hit_counter[l] + cov2.lines_hit_counter[l]
            for l in cov1.lines_hit_counter
        }
        return LinesCoverage(summarized_lines_coverage)

    def compute_coverage_relation(self, other: "LinesCoverage") -> Tuple[float, float]:
        lines_only_covered_by_self = 0
        lines_only_covered_by_other = 0
        for program_line in self.relevant_program_lines:
            if (
                self.lines_hit_counter[program_line]
                <= 0
                < other.lines_hit_counter[program_line]
            ):
                lines_only_covered_by_other += 1
            if (
                other.lines_hit_counter[program_line]
                <= 0
                < self.lines_hit_counter[program_line]
            ):
                lines_only_covered_by_self += 1
        if self.lines_total == 0:
            return 0.0, 0.0
        return (
            float(lines_only_covered_by_self) / float(self.lines_total),
            float(lines_only_covered_by_other) / float(self.lines_total),
        )

    def is_program_line_covered(self, pl) -> bool:
        return self.lines_hit_counter[pl] > 0

    def is_coverage_for_program_line_extended(self, other: "LinesCoverage", pl) -> bool:
        return not self.is_program_line_covered(pl) and other.is_program_line_covered(
            pl
        )


class BranchesCoverage(CoverageComparable):
    """
    Contains a dictionary with program lines as keys and two-element lists with booleans as values. For each program
    line a corresponding list exists to state whether branch one and whether branch two are hit.
    Note that the values can be wrong because getting branch coverage with lcov does NOT WORK so far!
    If there will be a solution later to fix this issue it might be interesting to store how often the branches
    have been taken and not only whether they have been taken. In consequence, this class might be refactored.

    Two-element list 'value' at a certain program line:
    # value[0] == False and value[1] == False: This coverage is not possible
    # value[0] == False and value[1] == True: Only "if" branch executed
    # value[0] == True and value[1] == False: only "else" branch executed
    # value[0] == True and value[1] == True: "if" branch and "else" branch executed
    """

    def __init__(self, branches_hit_counter: Dict[int, List[bool]]):
        self.branches_hit_counter = branches_hit_counter

    @property
    def branches_total(self):
        return len(self.branches_hit_counter) * 2

    @property
    def branches_hit(self):
        hit = 0
        for value in self.branches_hit_counter.values():
            # hit is increased with two when both branches are executed
            if value[0]:
                hit += 1
            if value[1]:
                hit += 1
        return hit

    @property
    def relevant_program_lines(self):
        return self.branches_hit_counter.keys()

    @property
    def coverage_hit(self):
        return self.branches_hit

    @staticmethod
    def merge(cov1: "BranchesCoverage", cov2: "BranchesCoverage") -> "BranchesCoverage":
        summarized_branches_coverage = {}
        for line in cov1.relevant_program_lines:
            summarized_branches_coverage[line] = [False, False]
            for i in (0, 1):
                summarized_branches_coverage[line][i] = (
                    cov1.branches_hit_counter[line][i]
                    or cov2.branches_hit_counter[line][i]
                )
        return BranchesCoverage(summarized_branches_coverage)

    def compute_coverage_relation(
        self, other: "BranchesCoverage"
    ) -> Tuple[float, float]:
        number_branches_taken_only_self = 0
        number_branches_taken_only_other = 0
        for program_line in self.relevant_program_lines:
            branches_taken_self = self.branches_hit_counter[program_line]
            branches_taken_other = other.branches_hit_counter[program_line]
            if branches_taken_self[0] <= 0 < branches_taken_other[0]:
                number_branches_taken_only_other += 1
            if branches_taken_other[0] <= 0 < branches_taken_self[0]:
                number_branches_taken_only_self += 1
            if branches_taken_self[1] <= 0 < branches_taken_other[1]:
                number_branches_taken_only_other += 1
            if branches_taken_other[1] <= 0 < branches_taken_self[1]:
                number_branches_taken_only_self += 1
        return (
            float(number_branches_taken_only_self) / float(self.branches_total),
            float(number_branches_taken_only_other) / float(other.branches_total),
        )

    def is_program_line_covered(self, pl):
        return pl in self.relevant_program_lines and all(self.branches_hit_counter[pl])

    def is_coverage_for_program_line_extended(
        self, other: "BranchesCoverage", pl
    ) -> bool:
        branch_taken_self = self.branches_hit_counter[pl]
        branch_taken_other = other.branches_hit_counter[pl]
        return (not branch_taken_self[0] and branch_taken_other[0]) or (
            not branch_taken_self[1] and branch_taken_other[1]
        )


class TestCoverage:
    """
    Contains the line coverage, branch coverage and conditions coverage. One of these coverage kinds can be
    extracted by using the coverage goal in the execution.
    The dictionary test_vector_results stores for each test vector the test result.
    """

    def __init__(
        self,
        file_name: str,
        test_vector_results: Dict[eu.TestVector, eu.TestResult],
        lines_coverage: Optional[LinesCoverage] = None,
        branches_coverage: Optional[BranchesCoverage] = None,
        conditions_coverage: Optional[ConditionsCoverage] = None,
    ):
        self.filename = file_name
        self.test_vector_results = test_vector_results
        self.lines_coverage = lines_coverage
        self.branches_coverage = branches_coverage
        self.conditions_coverage = conditions_coverage

    @property
    def test_vectors(self):
        return [*self.test_vector_results]

    @property
    def lines_hit(self):
        if self.lines_coverage is None:
            return 0
        return self.lines_coverage.lines_hit

    @property
    def lines_total(self):
        if self.lines_coverage is None:
            return 0
        return self.lines_coverage.lines_total

    @property
    def branches_hit(self):
        if self.branches_coverage is None:
            return 0
        return self.branches_coverage.branches_hit

    @property
    def branches_total(self):
        if self.branches_coverage is None:
            return 0
        return self.branches_coverage.branches_total

    @property
    def conditions_hit(self):
        if self.conditions_coverage is None:
            return 0
        return self.conditions_coverage.conditions_hit

    @property
    def conditions_total(self):
        if self.conditions_coverage is None:
            return 0
        return self.conditions_coverage.conditions_total

    @property
    def line_coverage(self):
        if self.lines_coverage is None:
            return 0
        if self.lines_total == 0:
            return 1.0
        return round(float(self.lines_hit) / float(self.lines_total) * 100, 2)

    @property
    def branch_coverage(self):
        if self.branches_coverage is None:
            return 0
        if self.branches_coverage.branches_total == 0:
            return 1.0
        return round(
            float(self.branches_coverage.branches_hit)
            / float(self.branches_coverage.branches_total)
            * 100,
            2,
        )

    @property
    def condition_coverage(self):
        if self.conditions_coverage is None:
            return 0
        if self.conditions_total == 0:
            return 1.0
        return round(float(self.conditions_hit) / float(self.conditions_total) * 100, 2)

    def coverage_type(self, goal) -> Optional[CoverageComparable]:
        if goal in [eu.COVER_BRANCHES, eu.COVER_ERRORS]:
            return self.branches_coverage
        if goal == eu.COVER_CONDITIONS:
            return self.conditions_coverage
        if goal == eu.COVER_LINES:
            return self.lines_coverage
        raise AssertionError("Unhandled coverage goal: {}".format(goal))

    def get_coverage_for_goal(self, goal) -> float:
        if goal in [eu.COVER_BRANCHES, eu.COVER_ERRORS]:
            return self.branch_coverage
        if goal == eu.COVER_CONDITIONS:
            return self.condition_coverage
        if goal == eu.COVER_LINES:
            return self.line_coverage
        raise AssertionError("Unhandled coverage goal: {}".format(goal))

    def test_vectors_as_string(self):
        # Normally this method is called when the test coverage for an individual test is printed. If so this method
        # returns the origin of the only test vector.
        out = ""
        separator = " | "
        i = 0
        while i < len(self.test_vectors) - 1:
            out += self.test_vectors[i].origin
            out += separator
        out += self.test_vectors[i].origin
        return out

    @staticmethod
    def merge(cov1: "TestCoverage", cov2: "TestCoverage") -> "TestCoverage":
        assert cov1.filename == cov2.filename
        summarized_test_vector_results = {
            **cov2.test_vector_results,
            **cov1.test_vector_results,
        }
        summarized_lines_coverage = LinesCoverage.merge(
            cov1.lines_coverage, cov2.lines_coverage
        )
        summarized_branches_coverage = BranchesCoverage.merge(
            cov1.branches_coverage, cov2.branches_coverage
        )
        summarized_conditions_coverage = ConditionsCoverage.merge(
            cov1.conditions_coverage, cov2.conditions_coverage
        )
        return TestCoverage(
            cov1.filename,
            summarized_test_vector_results,
            summarized_lines_coverage,
            summarized_branches_coverage,
            summarized_conditions_coverage,
        )


def remove_prefix(line, prefix):
    return line[len(prefix) :]


def _examine_line_with_condition(
    line_with_condition_info,
    branch_condition_hit_counter_dic,
    conditions_entries: List[ConditionsEntry],
):
    chunks = line_with_condition_info.split(",")
    # chunks should be [program_line, block-number, branch-number, taken]
    assert len(chunks) == 4
    program_line = chunks[0]
    condition_index = chunks[2]
    number_of_condition_taken = chunks[3]
    if program_line.isdigit() and condition_index.isdigit():
        program_line = int(program_line)
        condition_index = int(condition_index)
    else:
        logging.error(
            "Trace file corrupted. Program line or branch number not a number"
        )
        return
    if number_of_condition_taken == TRACE_FILE_CONDITION_NOT_VISITED:
        number_of_condition_taken = 0
    else:
        number_of_condition_taken = int(number_of_condition_taken)

    _append_to_branch_coverage(
        branch_condition_hit_counter_dic,
        program_line,
        condition_index,
        number_of_condition_taken,
    )
    _append_to_conditions_entries(
        conditions_entries, program_line, condition_index, number_of_condition_taken
    )


# Not working with lcov so far
def _append_to_branch_coverage(
    branch_hit_counter: Dict, program_line, condition_index, number_of_condition_taken
):
    """
    Currently this method delivers wrong branch coverages because lcov does not provide a pattern in its trace files
    which we can use to find out which branch is taken when looking at the conditions.
    :param branch_hit_counter:
    :param program_line: the program line where this branching appears
    :param condition_index:  a unique value to address the condition
    :param number_of_condition_taken: the number how often the condition is taken
    :return:
    """
    if program_line not in branch_hit_counter.keys():
        branch_hit_counter[program_line] = [False, False]
    if number_of_condition_taken >= 1:
        # a branch is fully executed when at least the condition is one time satisfied and one time not
        # branch number even when condition not satisfied
        # branch number odd when condition satisfied
        if condition_index % 2 == 0:
            branch_hit_counter[program_line][0] = True
        else:
            branch_hit_counter[program_line][1] = True


def _append_to_conditions_entries(
    conditions_entries: List[ConditionsEntry],
    program_line,
    condition_index,
    number_of_condition_taken,
):
    """
    Takes the condition_entry from conditions_entries by using the program_line. If no condition_entry is found
    a new condition_entry is created. The value for the key branch_index is overwritten with number_of_branch_taken.
    :param conditions_entries: the list of conditions_entries found so far in the trace file
    :param program_line: the program line for which branch_index and number_of_branch_taken is applied
    :param condition_index: a unique value to address the condition
    :param number_of_condition_taken: the number how often the condition is taken
    :return:
    """
    condition_entry = next(
        iter([e for e in conditions_entries if e.program_line == program_line]), None
    )
    if condition_entry is None:
        condition_entry = ConditionsEntry(program_line, {})
        conditions_entries.append(condition_entry)
    condition_entry.set_condition_to_hit_counter(
        condition_index, number_of_condition_taken
    )


def get_test_coverage_from_trace_file(
    program_name, trace_file, test_vector_with_result
) -> TestCoverage:
    lines_hit_counter_dic = {}
    lines_hit = 0
    lines_found = 0
    branches_hit_counter = {}
    conditions_taken = 0
    conditions_found = 0
    conditions_entries = []
    if os.path.exists(trace_file):
        lcov_sector = LcovSector.BEFORE_TEST_RECORD.value
        with open(trace_file) as file:
            for line in file:
                line = line.strip()
                if lcov_sector == LcovSector.BEFORE_TEST_RECORD.value:
                    if line.startswith(LcovPrefix.FILEPATH.value):
                        absolute_file_path = remove_prefix(
                            line, LcovPrefix.FILEPATH.value
                        )
                        if os.path.basename(absolute_file_path) == program_name:
                            lcov_sector = LcovSector.IN_TEST_RECORD.value

                elif lcov_sector == LcovSector.IN_TEST_RECORD.value:

                    if line.startswith(
                        LcovPrefix.BRANCH_LINE_CONDITION_HIT_COUNTER.value
                    ):
                        branch_line_information = remove_prefix(
                            line, LcovPrefix.BRANCH_LINE_CONDITION_HIT_COUNTER.value
                        )
                        _examine_line_with_condition(
                            branch_line_information,
                            branches_hit_counter,
                            conditions_entries,
                        )
                    elif line.startswith(LcovPrefix.CONDITIONS_FOUND.value):
                        conditions_found = int(
                            remove_prefix(line, LcovPrefix.CONDITIONS_FOUND.value)
                        )
                    elif line.startswith(LcovPrefix.CONDITIONS_TAKEN.value):
                        conditions_taken = int(
                            remove_prefix(line, LcovPrefix.CONDITIONS_TAKEN.value)
                        )
                    elif line.startswith(LcovPrefix.LINE_HIT_COUNTER.value):
                        line_with_counter = remove_prefix(
                            line, LcovPrefix.LINE_HIT_COUNTER.value
                        )
                        chunks = line_with_counter.split(",")
                        # chunks should be [program-line, hit-counter]
                        assert len(chunks) == 2
                        lines_hit_counter_dic[int(chunks[0])] = int(chunks[1])
                    elif line.startswith(LcovPrefix.LINES_FOUND.value):
                        lines_found = int(
                            remove_prefix(line, LcovPrefix.LINES_FOUND.value)
                        )
                    elif line.startswith(LcovPrefix.LINES_NONZERO_HIT_COUNTER.value):
                        lines_hit = int(
                            remove_prefix(
                                line, LcovPrefix.LINES_NONZERO_HIT_COUNTER.value
                            )
                        )
                    elif line.startswith(LcovPrefix.END_OF_RECORD.value):
                        break

                else:
                    break

    else:
        logging.debug(
            "File '%s' does not exist. Returning empty test coverage", trace_file
        )

    lines_coverage = LinesCoverage(lines_hit_counter_dic)
    assert lines_hit == lines_coverage.lines_hit
    assert lines_found == lines_coverage.lines_total

    conditions_coverage = ConditionsCoverage(conditions_entries)
    assert conditions_found == conditions_coverage.conditions_total
    assert conditions_taken == conditions_coverage.conditions_hit

    branches_coverage = BranchesCoverage(branches_hit_counter)

    return TestCoverage(
        trace_file,
        test_vector_with_result,
        lines_coverage,
        branches_coverage,
        conditions_coverage,
    )


def write_test_coverages_to_dir(output_dir, test_coverages, file_name):
    output_file = os.path.join(output_dir, file_name)
    with open(output_file, mode="w") as individual_test_cov_file:
        writer = csv.writer(
            individual_test_cov_file, delimiter=DELIMITER_TEST_COVERAGES
        )
        writer.writerow(HEADER)
        _write_csv_rows_from_test_coverages(writer, test_coverages)


def _write_csv_rows_from_test_coverages(writer, test_coverages):
    for test_coverage in test_coverages:
        writer.writerow(
            [
                test_coverage.test_vectors_as_string(),
                test_coverage.line_coverage,
                test_coverage.branch_coverage,
                test_coverage.condition_coverage,
            ]
        )


def create_trace_file_and_get_test_coverage(
    program_name,
    data_file,
    output_tracefile,
    test_vector_with_result,
    gcov_tool=LLVM_GCOV_BINARY,
):
    if os.path.exists(data_file):
        cmd = [
            "lcov",
            "--gcov-tool",
            gcov_tool,
            "--rc",
            "lcov_branch_coverage=1",
            "-c",
            "-d",
            ".",
            "--no-recursion",
            "-o",
            output_tracefile,
        ]
        eu.execute(cmd, quiet=True)
        if os.path.exists(output_tracefile):
            test_coverage = get_test_coverage_from_trace_file(
                program_name, output_tracefile, test_vector_with_result
            )
            return test_coverage
    raise CoverageCreationError("Trace file '%s' not created." % output_tracefile)
