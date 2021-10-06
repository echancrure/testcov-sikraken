#!/usr/bin/env python3

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
import os, sys, subprocess, shutil, filecmp

SOURCE_FILES = "test/programs"
CONVERTED_FILES = "labeler-converted-files"
TEMP_FOLDER = "__temp"

found_missmatch = False
for filename in os.listdir(source_path):
    if(filename.endswith((".c",".cpp",".h",".hpp"))):
        print("Processing '" + filename + "' from '" + source_path + "'...")
        shutil.copy(os.path.join(source_path, filename), dest_path)
        if filecmp.cmp(os.path.join(dest_path, filename), os.path.join(converted_path, filename)):
            print("Files are equal")
        else:
            print("FILES DO NOT MATCH!")
            found_missmatch = True
if found_missmatch:
    print("Test failed!")
else:
    print("Test succeded!")


def source_programs():
    test_dir = os.path.dirname(__file__)
    return os.listdir(os.path.join(test_dir, 'programs'))


def expected_outputs():
    test_dir = os.path.dirname(__file__)
    return os.path.join(test_dir, 'expected')


def labeler_bin():
    return "libtooling-label-adder/label-adder"


def test_labeler(source_programs, expected_outputs, labeler_bin):
    for program_file, expected_output in zip(source_programs, expected_outputs):
        assert _label(program_file, labeler_bin) == expected_output

def _label(program_file):
    subprocess.call(["libtooling-label-adder/labeler-ubuntu204-bin", "-no-info", "-in-place", os.path.join(dest_path, filename), "--"])

