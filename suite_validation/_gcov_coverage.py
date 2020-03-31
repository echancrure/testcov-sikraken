# testcov is tool for validation and execution of test suites.
# This file is part of testcov.
#
# Copyright (C) 2018 - 2020  Dirk Beyer
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
"""Module for test coverage with gcov"""

import os
from suite_validation import execution_utils as eu


def create_gcov_file(program_name, data_file, gcov_tool="gcov"):
    _run_gcov(data_file, gcov_tool)
    program_name = os.path.basename(program_name)
    gcov_file = program_name + ".gcov"
    if not os.path.exists(gcov_file):
        raise FileNotFoundError(gcov_file)
    return gcov_file


def _run_gcov(data_file, gcov_tool="gcov"):
    if not os.path.exists(data_file):
        raise FileNotFoundError(data_file)

    gcov_cmd = [gcov_tool, "-bc", data_file]
    return eu.execute(gcov_cmd, quiet=True)
