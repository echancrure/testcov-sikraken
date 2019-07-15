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

from typing import Dict
from typing import Tuple
from typing import List
from abc import ABCMeta, abstractmethod
from suite_validation import execution_utils as eu

# Constants for csv output
FILE_NAME_TEST_COVERAGES = "individual-test-coverages.csv"
LINES_COVERED = "Line Coverage"
BRANCHES_COVERED = "Branch Coverage"
CONDITIONS_COVERED = "Condition Coverage"
TEST = "Test"
HEADER = [TEST, LINES_COVERED, BRANCHES_COVERED, CONDITIONS_COVERED]
DELIMITER_TEST_COVERAGES = "\t"

MODULE_DIRECTORY = os.path.join(os.path.dirname(__file__), os.path.pardir)

LCOV_WITH_BRANCH_COVERAGE = "lcov_branch_coverage=1"
LCOV_NO_RECURSION = "--no-recursion"
LCOV_USED_GCOV_TOOL = os.path.join(MODULE_DIRECTORY, "bin/llvm-gcov")

LCOV_COMMAND_PREFIX = [
    "lcov",
    "--gcov-tool",
    LCOV_USED_GCOV_TOOL,
    "--rc",
    LCOV_WITH_BRANCH_COVERAGE,
]

TRACE_FILE_CONDITION_NOT_VISITED = "-"


def divide(x, y):
    return float(x) / float(y)


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
    A class that implements CoverageComparable must be able to compute the coverage relation between an object of the class
    and another object of the same class. The computation of a coverage relation must return two values: The first
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


class ConditionsEntry(CoverageComparable):
    def __init__(self, program_line: int, conditions_hit_counter: Dict[int, int]):
        self.program_line = program_line
        self.conditions_hit_counter: Dict[int, int] = conditions_hit_counter

    def same_program_line(self, other: "ConditionsEntry") -> bool:
        return self.program_line == other.program_line

    @property
    def conditions_total(self) -> int:
        return len(self.conditions_hit_counter.keys())

    @property
    def conditions_hit(self) -> int:
        number_conditions_taken = 0
        for value in self.conditions_hit_counter.values():
            if value > 0:
                number_conditions_taken += 1
        return number_conditions_taken

    def set_condition_to_hit_counter(self, index: int, number_of_condition_taken: int):
        self.conditions_hit_counter[index] = number_of_condition_taken

    @staticmethod
    def merge(
        conditions_entry_1: "ConditionsEntry", conditions_entry_2: "ConditionsEntry"
    ) -> "ConditionsEntry":
        assert conditions_entry_1.program_line == conditions_entry_2.program_line
        summarized_conditions_hit_counter = {}
        for condition_index in conditions_entry_1.conditions_hit_counter.keys():
            summarized_conditions_hit_counter[condition_index] = (
                conditions_entry_1.conditions_hit_counter[condition_index]
                + conditions_entry_2.conditions_hit_counter[condition_index]
            )
        return ConditionsEntry(
            conditions_entry_1.program_line, summarized_conditions_hit_counter
        )

    def compute_coverage_relation(
        self, other: "ConditionsEntry"
    ) -> Tuple[float, float]:
        assert self.program_line == other.program_line
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        for key in self.conditions_hit_counter.keys():
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
        return (
            divide(conditions_only_covered_by_self, self.conditions_total),
            divide(conditions_only_covered_by_other, self.conditions_total),
        )


class ConditionsCoverage(CoverageComparable):
    def __init__(self, conditions_entries):
        self.conditions_entries = conditions_entries

    @property
    def conditions_hit(self) -> int:
        number_of_conditions_taken = 0
        for condition_entry in self.conditions_entries:
            number_of_conditions_taken += condition_entry.conditions_hit
        return number_of_conditions_taken

    @property
    def conditions_total(self) -> int:
        number_of_conditions_found = 0
        for condition_entry in self.conditions_entries:
            number_of_conditions_found += condition_entry.conditions_total
        return number_of_conditions_found

    @staticmethod
    def merge(
        conditions_coverage_1: "ConditionsCoverage",
        conditions_coverage_2: "ConditionsCoverage",
    ) -> "ConditionsCoverage":
        summarized_conditions_entries = []
        for entry_1 in conditions_coverage_1.conditions_entries:
            for entry_2 in conditions_coverage_2.conditions_entries:
                if entry_1.same_program_line(entry_2):
                    summarized_conditions_entries.append(
                        ConditionsEntry.merge(entry_1, entry_2)
                    )
        return ConditionsCoverage(summarized_conditions_entries)

    def compute_coverage_relation(
        self, other: "ConditionsCoverage"
    ) -> Tuple[float, float]:
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        for conditions_self in self.conditions_entries:
            for conditions_other in other.conditions_entries:
                if conditions_self.same_program_line(conditions_other):
                    conditions_only_covered_by_self, conditions_only_covered_by_other = (
                        conditions_only_covered_by_self,
                        conditions_only_covered_by_other
                        + conditions_self.compute_coverage_relation(conditions_other),
                    )
        if self.conditions_total == 0:
            return 0.0, 0.0
        return (
            divide(conditions_only_covered_by_self, self.conditions_total),
            divide(conditions_only_covered_by_other, self.conditions_total),
        )


class LinesCoverage(CoverageComparable):
    def __init__(self, program_lines_hit_counter: Dict[int, int]):
        self.lines_hit_counter: Dict[int, int] = program_lines_hit_counter

    @property
    def lines_hit(self) -> int:
        lines_taken = 0
        for program_line in self.lines_hit_counter.keys():
            if self.lines_hit_counter[program_line] > 0:
                lines_taken += 1
        return lines_taken

    @property
    def lines_total(self) -> int:
        return len(self.lines_hit_counter.keys())

    @staticmethod
    def merge(line_coverage_1: "LinesCoverage", line_coverage_2: "LinesCoverage"):
        summarized_lines_coverage = {}
        for line in line_coverage_1.lines_hit_counter.keys():
            summarized_lines_coverage[line] = (
                line_coverage_1.lines_hit_counter[line]
                + line_coverage_2.lines_hit_counter[line]
            )
        return LinesCoverage(summarized_lines_coverage)

    def compute_coverage_relation(self, other: "LinesCoverage") -> Tuple[float, float]:
        assert self.lines_total == other.lines_total
        diff = 0
        lines_self_covers_other = 0
        lines_other_covers_self = 0
        for program_line in self.lines_hit_counter.keys():
            if (
                self.lines_hit_counter[program_line] == 0
                and other.lines_hit_counter[program_line] > 0
            ):
                diff += 1
                lines_other_covers_self += 1
            if (
                self.lines_hit_counter[program_line] > 0
                and other.lines_hit_counter[program_line] == 0
            ):
                diff += 1
                lines_self_covers_other += 1
        if self.lines_total == 0:
            return 0.0, 0.0
        return (
            divide(lines_self_covers_other, self.lines_total),
            divide(lines_other_covers_self, self.lines_total),
        )


class BranchesCoverage(CoverageComparable):
    def __init__(self, branches_hit_counter: Dict):
        self.branches_hit_counter = branches_hit_counter

    @property
    def branches_total(self):
        return len(self.branches_hit_counter.keys()) * 2

    @property
    def branches_hit(self):
        branches_taken = 0
        for line_with_branch in self.branches_hit_counter.keys():
            conditions_executed = self.branches_hit_counter[line_with_branch]
            if conditions_executed[0]:
                branches_taken += 1
            if conditions_executed[1]:
                branches_taken += 1
        return branches_taken

    @staticmethod
    def merge(
        branch_coverage_1: "BranchesCoverage", branch_coverage_2: "BranchesCoverage"
    ) -> "BranchesCoverage":
        summarized_branches_coverage = {}
        for line in branch_coverage_1.branches_hit_counter.keys():
            if line not in summarized_branches_coverage.keys():
                summarized_branches_coverage[line] = [False, False]
            summarized_branches_coverage[line][0] = (
                summarized_branches_coverage[line][0]
                or branch_coverage_1.branches_hit_counter[line][0]
            )
            summarized_branches_coverage[line][1] = (
                summarized_branches_coverage[line][1]
                or branch_coverage_1.branches_hit_counter[line][1]
            )
        for line in branch_coverage_2.branches_hit_counter.keys():
            if line not in summarized_branches_coverage.keys():
                summarized_branches_coverage[line] = [False, False]
            summarized_branches_coverage[line][0] = (
                summarized_branches_coverage[line][0]
                or branch_coverage_2.branches_hit_counter[line][0]
            )
            summarized_branches_coverage[line][1] = (
                summarized_branches_coverage[line][1]
                or branch_coverage_2.branches_hit_counter[line][1]
            )
        return BranchesCoverage(summarized_branches_coverage)

    def compute_coverage_relation(
        self, other: "BranchesCoverage"
    ) -> Tuple[float, float]:
        # pylint: disable=unused-argument
        return 1.0, 1.0


class TestCoverage:
    def __init__(
        self,
        file_name,
        lines_coverage: LinesCoverage = None,
        branches_coverage: BranchesCoverage = None,
        conditions_coverage: ConditionsCoverage = None,
    ):
        self.filename = file_name
        self.lines_coverage: LinesCoverage = lines_coverage
        self.branches_coverage: BranchesCoverage = branches_coverage
        self.conditions_coverage: ConditionsCoverage = conditions_coverage
        self.test_vector = ""
        self.result = ""

    def set_test_vector(self, test_vector):
        self.test_vector = test_vector

    def set_result(self, result):
        self.result = result

    @property
    def lines_hit(self):
        return self.lines_coverage.lines_hit

    @property
    def lines_total(self):
        return self.lines_coverage.lines_total

    @property
    def branches_hit(self):
        return self.branches_coverage.branches_hit

    @property
    def branches_total(self):
        return self.branches_coverage.branches_total

    @property
    def conditions_hit(self):
        return self.conditions_coverage.conditions_hit

    @property
    def conditions_total(self):
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

    @staticmethod
    def merge(
        test_coverage_1: "TestCoverage", test_coverage_2: "TestCoverage"
    ) -> "TestCoverage":
        assert test_coverage_1.filename == test_coverage_2.filename
        summarized_lines_coverage = LinesCoverage.merge(
            test_coverage_1.lines_coverage, test_coverage_2.lines_coverage
        )
        summarized_branches_coverage = BranchesCoverage.merge(
            test_coverage_1.branches_coverage, test_coverage_2.branches_coverage
        )
        summarized_conditions_coverage = ConditionsCoverage.merge(
            test_coverage_1.conditions_coverage, test_coverage_2.conditions_coverage
        )
        return TestCoverage(
            test_coverage_1.filename,
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
    condition_entry = None
    for entry in conditions_entries:
        if entry.program_line == program_line:
            condition_entry = entry
    if condition_entry is None:
        condition_entry = ConditionsEntry(program_line, {})
        conditions_entries.append(condition_entry)
    condition_entry.set_condition_to_hit_counter(
        condition_index, number_of_condition_taken
    )


def get_test_coverage_from_trace_file(program_name, trace_file) -> TestCoverage:
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
        trace_file, lines_coverage, branches_coverage, conditions_coverage
    )


def write_test_coverages_to_dir(output_dir, overwrite, exec_results):
    output_file = os.path.join(output_dir, FILE_NAME_TEST_COVERAGES)
    write_header = False
    if not os.path.exists(output_file) or overwrite:
        write_header = True
    mode = "w" if overwrite else "a"
    with open(output_file, mode=mode) as individual_test_cov_file:
        writer = csv.writer(
            individual_test_cov_file, delimiter=DELIMITER_TEST_COVERAGES
        )
        if write_header:
            writer.writerow(HEADER)
        _write_csv_rows_from_test_coverages(writer, exec_results.coverage_tests)


def _write_csv_rows_from_test_coverages(writer, test_coverages):
    for test_coverage in test_coverages:
        writer.writerow(
            [
                test_coverage.test_vector.origin,
                test_coverage.line_coverage,
                test_coverage.branch_coverage,
                test_coverage.condition_coverage,
            ]
        )


def create_trace_file_and_get_test_coverage(program_name, data_file, output_tracefile):
    if os.path.exists(data_file):
        cmd = LCOV_COMMAND_PREFIX + [
            "-c",
            "-d",
            ".",
            LCOV_NO_RECURSION,
            "-o",
            output_tracefile,
        ]
        eu.execute(cmd, quiet=True)
        if os.path.exists(output_tracefile):
            test_coverage = get_test_coverage_from_trace_file(
                program_name, output_tracefile
            )
            return test_coverage
    raise CoverageCreationError("Trace file '%s' not created." % output_tracefile)
