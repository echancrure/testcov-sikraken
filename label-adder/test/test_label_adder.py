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


@pytest.fixture
def test_program_dir():
    test_dir = os.path.dirname(__file__)
    return os.path.join(test_dir, "programs")


@pytest.fixture(scope="session")
def source_files_and_expected_outcome():
    test_dir = os.path.dirname(__file__)
    source_programs = glob.glob(f"{test_dir}/programs/*")
    expected_contents = []
    for prog in source_programs:
        try:
            expected = next(
                iter(glob.glob(f"{test_dir}/expected/{os.path.basename(prog)}"))
            )
            with open(expected, "rb") as inp:
                expected_contents.append(inp.read())
        except StopIteration:
            expected_contents.append(None)
    return zip(source_programs, expected_contents)


@pytest.fixture
def labeler_bin():
    test_dir = os.path.dirname(__file__)
    label_adder_root = os.path.join(test_dir, os.path.pardir)
    return os.path.join(label_adder_root, "bin", "label-adder")


def test_labeler_output_compiles(
    source_files_and_expected_outcome, labeler_bin
):
    for program_file, _ in source_files_and_expected_outcome:
        actual_output = _label(program_file, labeler_bin)

        result = subprocess.run(['gcc', '-o', '/dev/null', '-x', 'c', '-include', 'test/sv-comp.h', '-'], input=actual_output, capture_output=True)
        assert result.returncode == 0, f"Error for {program_file}: {result.stderr.decode(encoding='UTF-8')}"



def _label(program_file, labeler_bin, options=[]):
    result = subprocess.run([labeler_bin, *options, program_file], capture_output=True)
    return result.stdout


def _number_goals(program_content):
    return program_content.count(b"Goal_")


def test_label_branches_if_without_else(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_simple-if.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--no-labels-function-start", "--no-labels-switch", "--no-labels-ternary"],
    )

    assert (
        _number_goals(result) == 2
    ), f"Wrong number of goals ({_number_goals(result)} instead of 2):\n{result}"

def test_label_branches_if_without_else_no_braces(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_ifWithoutBraces_ReachError.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--no-labels-function-start", "--no-labels-switch", "--no-labels-ternary"],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"

def test_label_branches_if_else_no_braces(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_if-else-without-braces.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--no-labels-function-start", "--no-labels-switch", "--no-labels-ternary"],
    )

    assert (
        _number_goals(result) == 2
    ), f"Wrong number of goals ({_number_goals(result)} instead of 2):\n{result}"



def test_label_branches_multipleBranchesAndConditions(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_multiple_branches_ReachError.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--no-labels-function-start", "--no-labels-switch", "--no-labels-ternary"],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"
