from enum import Enum
import os
import logging

ZERO = 0.00
FILE_NAME_TEST_COVERAGES = "individual-test-coverages"


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
            return ZERO
        return round(100 * float(self.lines_hit) / float(self.lines_found), 2)

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
            return ZERO
        return round(
            100
            * float(lines_with_branch_condition_executed)
            / float(possible_branch_conditions_executions),
            2,
        )

    def compute_branch_coverage(self):
        if self.branches_found <= 0:
            return ZERO
        return round(100 * float(self.branches_hit) / float(self.branches_found), 2)


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


def write_test_coverages_to_output(output_dir, program, exec_results):
    output_file = os.path.join(output_dir, FILE_NAME_TEST_COVERAGES)
    with open(output_file, "w") as outp:
        outp.write("Program: " + program + "\n")
        for test_coverage in exec_results.coverage_tests:
            outp.write("\n")
            outp.write("Test input: " + str(test_coverage.test_vector) + "\n")
            outp.write("Test result: " + test_coverage.result + "\n")
            outp.write(
                "Lines covered: "
                + as_percent_expression(test_coverage.compute_line_coverage())
                + "\n"
            )
            outp.write(
                "Branch conditions executed: "
                + as_percent_expression(
                    test_coverage.compute_branch_conditions_executed()
                )
                + "\n"
            )
            outp.write(
                "Branches covered: "
                + as_percent_expression(test_coverage.compute_branch_coverage())
                + "\n"
            )
        outp.close()


def as_percent_expression(value):
    return str(value) + "%"
