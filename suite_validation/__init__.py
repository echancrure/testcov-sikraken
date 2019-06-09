# tbf-testsuite-validator is tool for validation and execution of test suites.
# This file is part of tbf-testsuite-validator.
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
"""Main module of tbf-testsuite-validator."""

import argparse
import logging
import os
import re
import shutil
import zipfile
from suite_validation import execution
from suite_validation import execution_utils as eu
from suite_validation import test_coverage as test_cov

__VERSION__ = "v1.1-dev"

SUCCESSFUL_TESTSUITE_FOLDER = "test-suite"
SUCCESSFUL_TEST_NAME = "covering-test.xml"
"""Name of the file a successful test will be written to."""
SUCCESSFUL_HARNESS_NAME = "covering-test.c"
"""Name of the file the executable harness of a successful test will be written to."""


class IllegalArgumentError(Exception):
    pass


def get_parser():
    parser = argparse.ArgumentParser(prog="tbf test-suite validator")

    parser.add_argument(
        "--goal",
        dest="goal_file",
        action="store",
        required=True,
        help="coverage goal file",
    )

    parser.add_argument(
        "--timelimit-per-run",
        dest="timelimit_per_run",
        action="store",
        type=int,
        default=20,
        help="timelimit for each single test execution",
    )

    parser.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        default=True,
        help="don't overwrite existing files (e.g., the harness or executable)",
    )

    parser.add_argument(
        "--output",
        dest="output_dir",
        action="store",
        default="output",
        help="output directory to write to",
    )

    parser.add_argument("--version", "-v", action="version", version=__VERSION__)

    machine_model_args = parser.add_mutually_exclusive_group()
    machine_model_args.add_argument(
        "-32",
        dest="machine_model",
        action="store_const",
        const=eu.MACHINE_MODEL_32,
        help="Use 32 bit machine model",
    )
    machine_model_args.add_argument(
        "-64",
        dest="machine_model",
        action="store_const",
        const=eu.MACHINE_MODEL_64,
        help="Use 64 bit machine model",
    )

    parser.add_argument(
        "--test-suite",
        dest="test_suite",
        action="store",
        help="zip-file that contains test suite",
        required=True,
    )

    parser.add_argument(
        "--sequence-file",
        dest="print_seq_file",
        action="store",
        default=None,
        help="print sequence of accumulated coverage per executed test to file",
        required=False,
    )

    parser.add_argument(
        "--individual-test-coverage",
        dest="individual_test_cov",
        action="store_true",
        default=False,
        help="print coverage of each test to file",
    )

    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="show messages verbose",
    )

    parser.add_argument("file", action="store", help="program file")

    return parser


def parse():
    parser = get_parser()
    args = parser.parse_args()

    if args.machine_model is None:
        args.machine_model = eu.MACHINE_MODEL_32

    args.goal = parse_coverage_goal_file(args.goal_file)
    args.stop_after_success = args.goal == eu.COVER_ERRORS

    return args


def _write_test_to_output(
    program_file, test_container, successful_test, overwrite, output_dir
):
    """
    Writes, for the given test, the original XML definition and an executable harness
    to the current working directory.

    :param str program_file: Path to the program file.
    :param str test_container: Path to the zip-file that contains the successful test
    :param utils.TestVector successful_test: Test vector to create files for.
    :param bool overwrite: Whether to overwrite existing files.
    :param str output_dir: Output directory to write into.
    """
    successful_test_file = successful_test.origin
    test_directory = os.path.dirname(successful_test_file)
    metadata_file = os.path.join(test_directory, eu.METADATA_XML_NAME)
    _copy_file(
        metadata_file, test_container, output_dir, eu.METADATA_XML_NAME, overwrite
    )

    _copy_file(
        successful_test_file,
        test_container,
        output_dir,
        SUCCESSFUL_TEST_NAME,
        overwrite,
    )

    test_c_file = os.path.join(output_dir, SUCCESSFUL_HARNESS_NAME)
    harness_content = execution.HarnessCreator().convert(program_file, successful_test)
    if not overwrite and os.path.exists(test_c_file):
        logging.info("Not overwriting %s", test_c_file)
    else:
        with open(program_file) as progr_inp:
            harness_content = progr_inp.read() + harness_content
        with open(test_c_file, "w+") as outp:
            outp.write(harness_content)
    logging.info("Successful test data written to %s", SUCCESSFUL_TESTSUITE_FOLDER)


def _copy_file(
    relative_file_path, container, dest_directory, dest_name, overwrite=True
):
    file_dest = os.path.join(dest_directory, dest_name)
    if not overwrite and os.path.exists(file_dest):
        logging.info("Not overwriting %s", file_dest)
        return
    os.makedirs(dest_directory, exist_ok=True)

    logging.debug(
        "Copying %s from %s to %s/%s",
        relative_file_path,
        container,
        dest_directory,
        dest_name,
    )
    try:
        with zipfile.ZipFile(container) as inp_zip:
            source = inp_zip.open(relative_file_path)
            with source, open(file_dest, "wb+") as target:
                shutil.copyfileobj(source, target)
    except KeyError:
        logging.warning("No file %s in %s", relative_file_path, container)


def parse_coverage_goal_file(goal_file: str) -> str:
    with open(goal_file) as inp:
        content = inp.read().strip()
    prop_match = re.match(
        r"COVER\s*\(\s*init\s*\(\s*main\s*\(\s*\)\s*\)\s*,\s*FQL\s*\(COVER\s+EDGES\s*\((.*)\)\s*\)\s*\)",
        content,
    )
    if not prop_match:
        raise IllegalArgumentError(
            "No valid coverage goal specification in file {}: {}".format(
                goal_file, content[:100]
            )
        )

    goal = prop_match.group(1).strip()
    if goal not in eu.COVERAGE_GOALS.keys():
        raise IllegalArgumentError(
            "No valid coverage goal specification: {}".format(goal)
        )
    return eu.COVERAGE_GOALS[goal]


def main():
    args = parse()

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    logger = logging.getLogger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    exec_results = eu.SuiteExecutionResult()
    harness_file = os.path.join(args.output_dir, "harness.c")
    executable = os.path.join(args.output_dir, "a.out")
    compute_individuals = args.individual_test_cov
    try:
        executor = execution.SuiteExecutor(
            args.stop_after_success,
            args.timelimit_per_run,
            compute_sequence=args.print_seq_file is not None,
            overwrite_files=args.overwrite,
            harness_file_target=harness_file,
            compile_target=executable,
            compute_individuals=compute_individuals
        )

        executor.run(args.file, args.test_suite, args.machine_model, exec_results)

        if not exec_results.results:
            logging.warning(
                "No test case in exchange format found in '%s'", args.test_suite
            )

    except FileNotFoundError as e:
        logging.error(e)
    except execution.ExecutionError as e:
        logging.error(e.msg)
    finally:
        testsuite_folder = os.path.join(args.output_dir, SUCCESSFUL_TESTSUITE_FOLDER)
        if exec_results.successful_test:
            _write_test_to_output(
                args.file,
                args.test_suite,
                exec_results.successful_test,
                args.overwrite,
                testsuite_folder,
            )

        if exec_results.coverage_sequence and args.print_seq_file:
            if not os.path.exists(testsuite_folder):
                os.mkdir(testsuite_folder)
            seq_file = os.path.join(testsuite_folder, args.print_seq_file)
            if not args.overwrite and os.path.exists(seq_file):
                logging.info("Not overwriting %s", seq_file)
            else:
                with open(seq_file, "w") as outp:
                    outp.writelines(
                        [str(c) + "\n" for c in exec_results.coverage_sequence]
                    )

        if exec_results.coverage_tests:
            test_cov.write_individual_test_coverages_to_output(args.output_dir, args.file, exec_results)

        print()
        print("---Results---")
        print("Tests run:", len(exec_results.results))
        print("Lines covered:", exec_results.lines_executed)
        print("Branch conditions executed:", exec_results.branches_executed)
        print("Branches covered:", exec_results.branches_taken)

        if any(r == execution.COVERS for r in exec_results.results):
            verdict = "TRUE"
        else:
            verdict = "UNKNOWN"
        print("Result:", verdict)
