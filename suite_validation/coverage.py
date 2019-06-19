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
import shutil
import csv
from suite_validation import execution_utils as eu

# Constants for csv output
FILE_NAME_TEST_COVERAGES = "individual-test-coverages.csv"
LINES_COVERED = "Lines covered"
BRANCH_CONDITIONS_EXECUTED = "Branch conditions executed"
BRANCHES_COVERED = "Branches covered"
TEST = "Test"
HEADER = [TEST, LINES_COVERED, BRANCH_CONDITIONS_EXECUTED, BRANCHES_COVERED]
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


class TestCoverage:
    def __init__(
        self,
        file_name,
        lines_hit_counter_dic=None,
        lines_hit=0,
        lines_found=None,
        branch_condition_hit_counter_dic=None,
        conditions_taken=0,
        conditions_found=None,
    ):
        self.filename = file_name
        self.lines_hit_counter_dic = lines_hit_counter_dic
        self.lines_hit = lines_hit
        self.lines_total = lines_found
        self.branch_condition_hit_counter_dic = branch_condition_hit_counter_dic
        self.conditions_taken = conditions_taken
        self.conditions_total = conditions_found
        self.test_vector = ""
        self.result = ""

    def set_test_vector(self, test_vector):
        self.test_vector = test_vector

    def set_result(self, result):
        self.result = result

    @property
    def line_coverage(self):
        if self.lines_total is None:
            return 0
        if self.lines_total == 0:
            return 1.0
        return round(float(self.lines_hit) / float(self.lines_total) * 100, 2)

    @property
    def branch_coverage(self):
        lines_with_branch_condition_executed = 0
        for line_with_branch_condition in self.branch_condition_hit_counter_dic.keys():
            conditions_executed = self.branch_condition_hit_counter_dic[
                line_with_branch_condition
            ]
            if conditions_executed[0]:
                lines_with_branch_condition_executed += 1
            if conditions_executed[1]:
                lines_with_branch_condition_executed += 1
        if self.branches_total is None:
            return 0
        if self.branches_total == 0:
            return 1.0
        return round(
            float(lines_with_branch_condition_executed)
            / float(self.branches_total)
            * 100,
            2,
        )

    @property
    def branches_total(self):
        if self.branch_condition_hit_counter_dic is None:
            return None

        return len(self.branch_condition_hit_counter_dic.keys()) * 2

    @property
    def condition_coverage(self):
        if self.conditions_total is None:
            return 0
        if self.conditions_total == 0:
            return 1.0
        return round(
            float(self.conditions_taken) / float(self.conditions_total) * 100, 2
        )


def remove_prefix(line, prefix):
    return line[len(prefix) :]


def _examine_branch_line_condition(branch_line, branch_condition_hit_counter_dic):
    chunks = branch_line.split(",")
    # chunks should be [program_line, block-number, branch-number, taken]
    assert len(chunks) == 4
    program_line = chunks[0]
    branch_number = chunks[2]
    taken = chunks[3]
    if program_line.isdigit() and branch_number.isdigit():
        program_line = int(program_line)
        branch_number = int(branch_number)
    else:
        logging.error(
            "Trace file corrupted. Program line or branch number not a number"
        )
        return
    if program_line not in branch_condition_hit_counter_dic.keys():
        branch_condition_hit_counter_dic[program_line] = [False, False]
    if taken.isdigit() and int(taken) >= 1:
        # a branch is fully executed when at least the condition is one time satisfied and one time not
        # branch number even when condition not satisfied
        # branch number odd when condition satisfied
        if branch_number % 2 == 0:
            branch_condition_hit_counter_dic[program_line][0] = True
        else:
            branch_condition_hit_counter_dic[program_line][1] = True


def get_test_coverage_from_lcov_file(program_name, trace_file):
    lines_hit_counter_dic = {}
    lines_hit = 0
    lines_found = 0
    branches_hit_counter = {}
    conditions_taken = 0
    conditions_found = 0
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
                        _examine_branch_line_condition(
                            branch_line_information, branches_hit_counter
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
                        lines_hit_counter_dic[chunks[0]] = chunks[1]
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

    return TestCoverage(
        trace_file,
        lines_hit_counter_dic,
        lines_hit,
        lines_found,
        branches_hit_counter,
        conditions_taken,
        conditions_found,
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


def combine_tracefile_with_previous(trace_file, trace_file_summary):
    if os.path.exists(trace_file_summary):
        cmd = LCOV_COMMAND_PREFIX + [
            "-a",
            trace_file,
            "-a",
            trace_file_summary,
            "-o",
            trace_file_summary,
        ]
        eu.execute(cmd, quiet=True)
    else:
        shutil.move(trace_file, trace_file_summary)


def get_test_coverage_from_data_file(program_name, data_file, output_tracefile):
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
            test_coverage = get_test_coverage_from_lcov_file(
                program_name, output_tracefile
            )
            return test_coverage
    raise CoverageCreationError("Trace file '%s' not created." % output_tracefile)
