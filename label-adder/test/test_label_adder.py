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
    return os.path.join(label_adder_root, "..", "suite_validation", "label-adder")


def pytest_generate_tests(metafunc):
    if "labeler_param" in metafunc.fixturenames:
        metafunc.parametrize(
            "labeler_param",
            [
                ["--labels-branching-only"],
                ["--labels-function-start-only"],
                ["--labels-switch-only"],
                ["--labels-ternary-only"],
                ["--function-call-only", "--function-call=main"],
                ["--labels-branching-only", "--function-call=main"],
                [
                    "--labels-branching-only",
                    "--labels-ternary-only",
                    "--labels-switch-only",
                ],
                [],
            ],
        )
    if "test_program" in metafunc.fixturenames:
        metafunc.parametrize("test_program", source_files_and_expected_outcome())


def test_labeler_output_compiles(
    test_program, labeler_bin, test_program_dir, labeler_param
):
    program_file, _ = test_program
    actual_output = _label(program_file, labeler_bin, options=labeler_param)

    result = subprocess.run(
        [
            "gcc",
            "-o",
            "/dev/null",
            "-x",
            "c",
            "-include",
            f"{test_program_dir}/../sv-comp.h",
            "-",
        ],
        input=actual_output,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert (
        result.returncode == 0
    ), f"Error for {program_file} with parameter {labeler_param}: {result.stderr.decode(encoding='UTF-8')}"


def _label(program_file, labeler_bin, options=[]):
    result = subprocess.run(
        [labeler_bin, *options, program_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _number_goals(program_content):
    return program_content.count(b"Goal_")


def test_label_branches_if_without_else(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_simple-if.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 2
    ), f"Wrong number of goals ({_number_goals(result)} instead of 2):\n{result}"


def test_label_branches_if_without_else_no_braces(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_ifWithoutBraces_ReachError.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"


def test_label_branches_if_else_no_braces(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_if-else-without-braces.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 2
    ), f"Wrong number of goals ({_number_goals(result)} instead of 2):\n{result}"


def test_label_branches_multipleBranchesAndConditions(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_multiple_branches_ReachError.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"


def test_label_branches_elseif(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_if-elseif.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--labels-branching-only"],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"


def test_label_branches_and_main(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_if-elseif.c")

    result = _label(
        prog,
        labeler_bin,
        options=["--labels-branching-only", "--function-call=main"],
    )

    assert (
        _number_goals(result) == 5
    ), f"Wrong number of goals ({_number_goals(result)} instead of 5):\n{result}"


def test_label_while(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_while-singleline.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 2
    ), f"Wrong number of goals ({_number_goals(result)} instead of 2):\n{result}"


def test_label_for_loop(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_for.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"


def test_label_for_loop_empty(labeler_bin, test_program_dir):
    prog = os.path.join(test_program_dir, "test_for-empty.c")

    result = _label(
        prog,
        labeler_bin,
        options=[
            "--no-labels-function-start",
            "--no-labels-switch",
            "--no-labels-ternary",
        ],
    )

    assert (
        _number_goals(result) == 4
    ), f"Wrong number of goals ({_number_goals(result)} instead of 4):\n{result}"
