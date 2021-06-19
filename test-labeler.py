#!/usr/bin/env python3

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
import os, sys, subprocess, shutil, filecmp

SOURCE_FILES = "test"
CONVERTED_FILES = "labeler-converted-files"
TEMP_FOLDER = "__temp"

print("Started...")

source_path = os.path.join(os.getcwd(), SOURCE_FILES)
converted_path = os.path.join(os.getcwd(), CONVERTED_FILES)
dest_path = os.path.join(os.getcwd(), TEMP_FOLDER)

subprocess.call(["mkdir", dest_path])

found_missmatch = False
for filename in os.listdir(source_path):
    if(filename.endswith((".c",".cpp",".h",".hpp"))):
        print("Processing '" + filename + "' from '" + source_path + "'...")
        shutil.copy(os.path.join(source_path, filename), dest_path)
        subprocess.call(["libtooling-label-adder/labeler-ubuntu204-bin", "-no-info", "-in-place", os.path.join(dest_path, filename), "--"])
        if filecmp.cmp(os.path.join(dest_path, filename), os.path.join(converted_path, filename)):
            print("Files are equal")
        else:
            print("FILES DO NOT MATCH!")
            found_missmatch = True
if found_missmatch:
    print("Test failed!")
else:
    print("Test succeded!")

subprocess.call(["rm", "-r", dest_path])
