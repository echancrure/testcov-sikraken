#!/usr/bin/env python3

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
import glob
import os
import subprocess
import pytest

SOURCE_FILES = "test/programs"
CONVERTED_FILES = "labeler-converted-files"
TEMP_FOLDER = "__temp"

@pytest.fixture(scope="session")
def source_files_and_expected_outcome():
    test_dir = os.path.dirname(__file__)
    source_programs = glob.glob(f"{test_dir}/programs/*")
    expected_contents = []
    for prog in source_programs:
        try:
            expected = next(iter(glob.glob(f"{test_dir}/expected/{os.path.basename(prog)}")))
        except StopIteration:
            assert False, f"No program exists for {os.path.basename(prog)} in {test_dir}/expected"
        with open(expected, 'rb') as inp:
            expected_contents.append(inp.read())
    return zip(source_programs, expected_contents)


@pytest.fixture
def labeler_bin():
    test_dir = os.path.dirname(__file__)
    label_adder_root = os.path.join(test_dir, os.path.pardir)
    return os.path.join(label_adder_root, "bin", "label-adder")


def test_labeler(source_files_and_expected_outcome, labeler_bin):
    for program_file, expected_output in source_files_and_expected_outcome:
        actual_output = _label(program_file, labeler_bin) 
        
        assert actual_output == expected_output, f"Not matching for {os.path.basename(program_file)}"

def _label(program_file, labeler_bin):
    result = subprocess.run([labeler_bin, program_file], capture_output=True)
    return result.stdout
