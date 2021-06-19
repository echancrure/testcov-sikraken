#!/usr/bin/env python3

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
import os, shutil, subprocess

SOURCE_FILES = "test"
CONVERTED_FILES = "labeler-converted-files"

source_path = os.path.join(os.getcwd(), SOURCE_FILES)
converted_path = os.path.join(os.getcwd(), CONVERTED_FILES)

subprocess.call(["rm", "-r", converted_path])
subprocess.call(["mkdir", converted_path])

for filename in os.listdir(source_path):
    if(filename.endswith((".c",".cpp",".h",".hpp"))):
        print("Copying '" + filename + "' from '" + source_path + "'...")
        shutil.copy(os.path.join(source_path, filename), converted_path)
        subprocess.call(["libtooling-label-adder/labeler-ubuntu204-bin", "-no-info", "-in-place", os.path.join(converted_path, filename), "--"])
