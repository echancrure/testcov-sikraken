# testsuite-validator is tool for validation and execution of test suites.
# This file is part of testsuite-validator.
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
"""Main module of testsuite-validator."""

import argparse
import logging
import os
import re
import shutil
import zipfile
from suite_validation import execution
from suite_validation import execution_utils as eu
from suite_validation import coverage as cov
from suite_validation import metadata_utils

__VERSION__ = "v1.1-dev"

__NAME__ = "test-suite validator"

SUCCESSFUL_TESTSUITE_FOLDER = "test-suite"
SUCCESSFUL_TEST_NAME = "covering-test.xml"
"""Name of the file a successful test will be written to."""
SUCCESSFUL_HARNESS_NAME = "covering-test.c"
"""Name of the file the executable harness of a successful test will be written to."""
REDUCED_TESTSUITE_NAME = "reduced-suite.zip"


class IllegalArgumentError(Exception):
    pass


def get_parser():
    parser = argparse.ArgumentParser(prog="test-suite validator")

    parser.add_argument("--version", "-v", action="version", version=__VERSION__)

    parser.add_argument(
        "--goal",
        dest="goal_file",
        action="store",
        required=True,
        help="coverage goal file",
    )

    parser.add_argument(
        "--test-suite",
        dest="test_suite",
        action="store",
        help="zip-file that contains test suite",
        required=True,
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
        "--output",
        dest="output_dir",
        action="store",
        default="output",
        help="output directory to write to",
    )

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
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="show messages verbose",
    )

    parser.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        default=True,
        help="don't overwrite existing files (e.g., the harness or executable)",
    )

    parser.add_argument(
        "--no-sequence-file",
        dest="print_seq_file",
        action="store_const",
        const=None,
        default="coverage.seq",
        help="don't print sequence of accumulated coverage per executed test to file",
        required=False,
    )

    parser.add_argument(
        "--no-individual-test-coverage",
        dest="individual_test_cov",
        action="store_false",
        default=True,
        help="don't print coverage of each test to file",
    )

    parser.add_argument(
        "--no-create-reduced-suite",
        dest="reduce_tests",
        action="store_false",
        default=True,
        help="don't create a reduced test suite",
        required=False,
    )

    parser.add_argument(
        "--no-plots",
        dest="write_plots",
        action="store_false",
        default=True,
        help="don't create plots for coverage statistics",
        required=False,
    )

    parser.add_argument("file", action="store", help="program file")

    return parser


def parse():
    parser = get_parser()
    args = parser.parse_args()

    if args.machine_model is None:
        args.machine_model = eu.MACHINE_MODEL_32

    args.goal = parse_coverage_goal_file(args.goal_file)
    args.check_for_error = args.goal == eu.COVER_ERRORS

    return args


def _write_tests_to_suite(
    program_file, origin_suite, tests, overwrite, coverage_goal, output_suite
):
    """
    Writes the given tests from the given test suite to a new suite.

    :param str origin_suite: Path to the zip-file that contains the original test suite
    :param List[utils.TestVector] tests: Test vector to create files for.
    :param bool overwrite: Whether to overwrite existing files.
    :param str output_dir: Directory to write to.
    """
    if os.path.exists(output_suite) and overwrite:
        logging.debug(
            "File %s already exists and 'overwrite' option set - removing it.",
            output_suite,
        )
        os.remove(output_suite)

    output_metadata = _create_metadata(origin_suite, program_file, coverage_goal)
    with zipfile.ZipFile(output_suite, "a") as outp_zip:
        outp_zip.writestr(metadata_utils.METADATA_XML_NAME, output_metadata)

    test_names = [t.origin for t in tests]
    with zipfile.ZipFile(origin_suite) as inp_zip:
        for test in inp_zip.namelist():
            if test in test_names:
                _copy_file(test, origin_suite, output_suite, test)


def _create_metadata(origin_suite: str, program_file: str, coverage_goal: str) -> str:
    producer = " ".join([__NAME__, __VERSION__])
    return metadata_utils.create_for_reduced(
        origin_suite, producer, program_file, coverage_goal
    )


def _write_harness(program_file, test_vector, overwrite, output_dir):
    """
    Writes, for the given test, an executable harness to the output folder.

    :param str program_file: Path to the program file.
    :param eu.TestVector test_vector: test vector to create harness for.
    :param bool overwrite: Whether to overwrite existing files.
    :param str output_dir: Output directory to write into.
    """

    test_c_file = os.path.join(output_dir, SUCCESSFUL_HARNESS_NAME)
    harness_content = execution.HarnessCreator().convert(program_file, test_vector)
    if not overwrite and os.path.exists(test_c_file):
        logging.info("Not overwriting %s", test_c_file)
    else:
        with open(program_file) as progr_inp:
            harness_content = progr_inp.read() + harness_content
        with open(test_c_file, "w+") as outp:
            outp.write(harness_content)
    logging.info("Successful test data written to %s", SUCCESSFUL_TESTSUITE_FOLDER)


def _copy_file(relative_file_path, origin_container, dest_container, dest_name):
    logging.debug(
        "Copying %s from %s to %s/%s",
        relative_file_path,
        origin_container,
        dest_container,
        dest_name,
    )
    try:
        with zipfile.ZipFile(dest_container, "a") as outp_zip:
            if dest_name in outp_zip.namelist():
                logging.info(
                    "%s already exists in %s - not adding to the zip file, as it would be a duplicate",
                    dest_name,
                    dest_container,
                )
            else:
                with zipfile.ZipFile(origin_container) as inp_zip:
                    content = inp_zip.read(relative_file_path)
                outp_zip.writestr(dest_name, content)
    except KeyError:
        logging.warning("No file %s in %s", relative_file_path, origin_container)


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


def _print_suite_execution_results(exec_results):
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
            args.goal,
            args.timelimit_per_run,
            compute_sequence=args.print_seq_file is not None,
            reduce_tests=args.reduce_tests,
            overwrite_files=args.overwrite,
            harness_file_target=harness_file,
            compile_target=executable,
            compute_individuals=compute_individuals,
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
        if exec_results.successful_tests:
            _write_tests_to_suite(
                args.file,
                args.test_suite,
                exec_results.successful_tests,
                args.overwrite,
                args.goal,
                os.path.join(args.output_dir, REDUCED_TESTSUITE_NAME),
            )
            if args.check_for_error:
                # If at least one test covered an error,
                # make the first one into an executable harness
                _write_harness(
                    args.file,
                    exec_results.successful_tests[0],
                    args.overwrite,
                    args.output_dir,
                )

        if exec_results.coverage_sequence and args.print_seq_file:
            seq_file = os.path.join(args.output_dir, args.print_seq_file)
            if not args.overwrite and os.path.exists(seq_file):
                logging.info("Not overwriting %s", seq_file)
            else:
                with open(seq_file, "w") as outp:
                    outp.writelines(
                        [str(c) + "\n" for c in exec_results.coverage_sequence]
                    )

        if exec_results.coverage_tests:
            cov.write_test_coverages_to_dir(
                args.output_dir, args.overwrite, exec_results
            )
        if args.write_plots:
            try:
                from suite_validation import plotting

                plotting.create_plots(
                    exec_results, args.goal, args.output_dir, args.overwrite
                )
            except ImportError as e:
                logging.warning("Not plotting coverage statistics: %s", e.msg)

        print()
        _print_suite_execution_results(exec_results)
