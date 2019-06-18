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
from suite_validation import execution_utils as eu

FILE_NAME_TEST_COVERAGES = "individual-test-coverages"
LINES_COVERED = "Lines covered"

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


class LcovPrefix(Enum):
    FILEPATH = "SF:"
    BRANCH_LINE_CONDITION_HIT_COUNTER = "BRDA:"
    BRANCHES_FOUND = "BRF:"
    BRANCHES_HIT = "BRH:"
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
        lines_found=0,
        branch_condition_hit_counter_dic=None,
        branches_hit=0,
        branches_found=0,
    ):
        self.filename = file_name
        self.lines_hit_counter_dic = lines_hit_counter_dic
        self.lines_hit = lines_hit
        self.lines_found = lines_found
        self.branch_condition_hit_counter_dic = branch_condition_hit_counter_dic
        self.branches_hit = branches_hit
        self.branches_found = branches_found
        self.test_vector = ""
        self.result = ""
        if self.lines_hit_counter_dic is None:
            self.lines_hit_counter_dic = {}
        if self.branch_condition_hit_counter_dic is None:
            self.branch_condition_hit_counter_dic = {}

    def set_test_vector(self, test_vector):
        self.test_vector = test_vector

    def set_result(self, result):
        self.result = result

    def compute_line_coverage(self):
        if self.lines_found <= 0:
            return 1.0
        return round(float(self.lines_hit) / float(self.lines_found), 4)

    def compute_branch_conditions_executed(self):
        possible_branch_conditions_executions = (
            len(self.branch_condition_hit_counter_dic.keys()) * 2
        )
        lines_with_branch_condition_executed = 0
        for line_with_branch_condition in self.branch_condition_hit_counter_dic.keys():
            conditions_executed = self.branch_condition_hit_counter_dic[
                line_with_branch_condition
            ]
            if conditions_executed[0]:
                lines_with_branch_condition_executed += 1
            if conditions_executed[1]:
                lines_with_branch_condition_executed += 1
        if possible_branch_conditions_executions <= 0:
            return 1.0
        return round(
            float(lines_with_branch_condition_executed)
            / float(possible_branch_conditions_executions),
            4,
        )

    def compute_branch_coverage(self):
        if self.branches_found <= 0:
            return 1.0
        return round(float(self.branches_hit) / float(self.branches_found), 4)

    def get_coverage_ratios_as_percent_expressions(self):
        line_coverage = self.compute_line_coverage()
        branch_condition_coverage = self.compute_branch_conditions_executed()
        branch_coverage = self.compute_branch_coverage()
        return (
            str(round(line_coverage * 100, 2)) + "%",
            str(round(branch_condition_coverage * 100, 2)) + "%",
            str(round(branch_coverage * 100, 2)) + "%",
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
    branch_condition_hit_counter_dic = {}
    branches_hit = 0
    branches_found = 0
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
                            branch_line_information, branch_condition_hit_counter_dic
                        )
                    elif line.startswith(LcovPrefix.BRANCHES_FOUND.value):
                        branches_found = int(
                            remove_prefix(line, LcovPrefix.BRANCHES_FOUND.value)
                        )
                    elif line.startswith(LcovPrefix.BRANCHES_HIT.value):
                        branches_hit = int(
                            remove_prefix(line, LcovPrefix.BRANCHES_HIT.value)
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
        branch_condition_hit_counter_dic,
        branches_hit,
        branches_found,
    )


def write_test_coverages_to_dir(output_dir, program, exec_results):
    output_file = os.path.join(output_dir, FILE_NAME_TEST_COVERAGES)
    with open(output_file, "w") as outp:
        outp.write("Program: " + program + "\n")
        for test_coverage in exec_results.coverage_tests:
            outp.write("\n")
            outp.write("Test input: " + str(test_coverage.test_vector) + "\n")
            outp.write("Test result: " + test_coverage.result + "\n")
            lines_executed, branches_executed, branches_taken = (
                test_coverage.get_coverage_ratios_as_percent_expressions()
            )
            outp.write("Lines covered: " + lines_executed + "\n")
            outp.write("Branch conditions executed: " + branches_executed + "\n")
            outp.write("Branches covered: " + branches_taken + "\n")
        outp.close()


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
    logging.warning(
        "Trace file '%s' not created. Returning empty test coverage.", output_tracefile
    )
    return TestCoverage(program_name)
