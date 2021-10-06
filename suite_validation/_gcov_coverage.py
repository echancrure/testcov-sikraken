# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020  Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module for test coverage with gcov"""

import re
import os
from typing import Tuple
from collections import namedtuple
from suite_validation import execution_utils as eu

Coverage = namedtuple("Coverage", ("hits_percent", "count_total"))


class GcovError(Exception):
    pass


def create_gcov_file(
    program_name, data_file, gcov_tool="gcov"
) -> Tuple[str, eu.ExecutionResult]:
    execution_result = _run_gcov(data_file, gcov_tool)
    program_name = os.path.basename(program_name)
    gcov_file = program_name + ".gcov"
    if not os.path.exists(gcov_file):
        raise FileNotFoundError(gcov_file)
    return gcov_file, execution_result


def _run_gcov(data_file, gcov_tool="gcov"):
    if not os.path.exists(data_file):
        raise FileNotFoundError(data_file)

    gcov_cmd = [gcov_tool, "-bc", data_file]
    return eu.execute(gcov_cmd, quiet=True)


def parse_gcov_output(program_name, gcov_output, goal) -> Coverage:
    if eu.uses_line_coverage(goal):
        match = "Lines executed:"
    elif eu.uses_condition_coverage(goal) or eu.uses_branch_coverage(goal):
        # this is actually condition coverage, but use it for backwards-compatibility
        match = "Taken at least once:"
    else:
        raise GcovError(f"Unhandled coverage goal type {goal}")

    value_re = re.compile(r".*:\s*([0-9]+(.[0-9]+)?)% of ([0-9]+)")
    in_file = False
    for line in gcov_output.split("\n"):
        if line.startswith("File"):
            in_file = program_name in line
        if in_file and line.startswith(match):
            m = value_re.match(line)
            if not m:
                raise GcovError()
            return Coverage(hits_percent=float(m.group(1)), count_total=int(m.group(3)))
    raise GcovError("Expected coverage output not found in gcov output")
