# reduced_program testcov is tool for validation and execution of test suites.
# This file is part of testcov.
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
"""Main module of testcov."""

import argparse
import csv
import logging
import os
import re
import shutil
import zipfile
import numpy as np
from suite_validation import execution
from suite_validation import execution_utils as eu
from suite_validation import coverage as cov
from suite_validation import reduction_strategy as rs
from suite_validation import metadata_utils

__VERSION__ = "v3.0-16-g689dd44"

__NAME__ = "testcov"

# Constants for csv output
RESULTS_FILE = "results.csv"
DELIMITER_TEST_COVERAGES = ";"
CSV_HEADER_TEST = "Test"
CSV_HEADER_COVERAGE_INDIVIDUAL = "Coverage (individual)"
CSV_HEADER_COVERAGE_SEQUENCE = "Coverage (accumulated)"
CSV_HEADER_COVERAGE_REDUCED = "Part of reduced suite"
CSV_HEADER_RESULT = "Execution success"
CSV_HEADER_RETURNCODE = "Returncode"
CSV_HEADER_CPUTIME = "CPU-Time (s)"
CSV_HEADER_WALLTIME = "Wall-Time (s)"

SUCCESSFUL_TESTSUITE_FOLDER = "test-suite"
SUCCESSFUL_TEST_NAME = "covering-test.xml"
"""Name of the file a successful test will be written to."""
SUCCESSFUL_HARNESS_NAME = "covering-test.c"
"""Name of the file the executable harness of a successful test will be written to."""
REDUCED_TESTSUITE_NAME = "reduced-suite.zip"

VERDICT_DONE = "DONE"
VERDICT_UNKNOWN = "UNKNOWN"
VERDICT_TRUE = "TRUE"
VERDICT_ERROR = "ERROR"


class IllegalArgumentError(Exception):
    pass


def get_parser():
    parser = argparse.ArgumentParser(
        prog=__NAME__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

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
        default=3,
        help="timelimit for each single test execution",
    )

    parser.add_argument(
        "--memlimit",
        dest="memlimit",
        action="store",
        default="2GB",
        help="memory limit for each execution",
    )

    parser.add_argument(
        "--cpu-cores",
        dest="cpu_cores",
        action="store",
        type=int,
        default="1",
        help="cpu core limit for each execution",
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
        default=eu.MACHINE_MODEL_32,
        help="use 32 bit machine model",
    )
    machine_model_args.add_argument(
        "-64",
        dest="machine_model",
        action="store_const",
        const=eu.MACHINE_MODEL_64,
        default=eu.MACHINE_MODEL_32,
        help="use 64 bit machine model",
    )

    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="show messages verbose",
    )

    parser.add_argument(
        "--no-sequence",
        dest="print_seq",
        action="store_false",
        default=True,
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
        "--reduction",
        dest="reduce_tests",
        action="store",
        default=rs.BYORDER_REDUCTION,
        help="apply reduction strategy to create a reduced test suite. Possible options: {}, {}, {}".format(
            *rs.REDUCTION_STRATEGIES.keys()
        ),
        required=False,
    )

    parser.add_argument(
        "--reduction-output",
        dest="reduced_suite_name",
        action="store",
        default=REDUCED_TESTSUITE_NAME,
        help="Name to which reduced test suite is written",
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

    parser.add_argument(
        "--no-runexec",
        dest="use_runexec",
        action="store_false",
        default=True,
        help="Don't use runexec, but only containerexec. Necessary if no access to cgroups is possible. No resource limits will be considered.",
    )

    parser.add_argument(
        "--no-isolation",
        dest="use_isolation",
        action="store_false",
        default=True,
        help="Don't run tests in isolation. No resource limits will be considered and file modifications are possible.",
    )

    parser.add_argument("file", action="store", help="program file")

    return parser


def parse():
    parser = get_parser()
    args = parser.parse_args()

    args.goal = parse_coverage_goal_file(args.goal_file)
    args.check_for_error = args.goal == eu.COVER_ERRORS
    args.use_runexec = args.use_runexec and args.use_isolation

    return args


def _write_tests_to_suite(
    program_file, origin_suite, tests, coverage_goal, output_suite
):
    """
    Writes the given tests from the given test suite to a new suite.

    :param str origin_suite: Path to the zip-file that contains the original test suite
    :param List[utils.TestVector] tests: Test vector to create files for.
    :param str output_suite: Zip-file or directory to write to.
    """
    if os.path.exists(output_suite):
        logging.debug("File %s already exists - removing it.", output_suite)
        if os.path.isdir(output_suite):
            shutil.rmtree(output_suite, ignore_errors=True)
        else:
            os.remove(output_suite)

    output_metadata = _create_metadata(origin_suite, program_file, coverage_goal)
    if output_suite.endswith(".zip"):
        with zipfile.ZipFile(output_suite, "a") as outp_zip:
            outp_zip.writestr(metadata_utils.METADATA_XML_NAME, output_metadata)
    else:
        os.makedirs(output_suite, exist_ok=True)
        metadata_file = os.path.join(output_suite, metadata_utils.METADATA_XML_NAME)
        with open(metadata_file, "bw") as metadata_outp:
            metadata_outp.write(output_metadata)

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


def _write_harness(program_file, test_vector, output_dir):
    """
    Writes, for the given test, an executable harness to the output folder.

    :param str program_file: Path to the program file.
    :param eu.TestVector test_vector: test vector to create harness for.
    :param str output_dir: Output directory to write into.
    """

    test_c_file = os.path.join(output_dir, SUCCESSFUL_HARNESS_NAME)
    harness_content = execution.HarnessCreator().convert(program_file, test_vector)
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
        if dest_container.endswith(".zip"):
            with zipfile.ZipFile(dest_container, "a") as outp_zip:
                if dest_name in outp_zip.namelist():
                    logging.info(
                        "%s already exists in %s - not adding, as it would be a duplicate",
                        dest_name,
                        dest_container,
                    )
                else:
                    with zipfile.ZipFile(origin_container) as inp_zip:
                        content = inp_zip.read(relative_file_path)
                    outp_zip.writestr(dest_name, content)

        else:
            dest_file = os.path.join(dest_container, dest_name)
            if os.path.exists(dest_file):
                logging.info(
                    "%s already exists in %s - not adding, as it would be a duplicate",
                    dest_name,
                    dest_container,
                )
            else:
                parent_dir = os.path.dirname(dest_file)
                os.makedirs(parent_dir, exist_ok=True)
                with zipfile.ZipFile(origin_container) as inp_zip:
                    content = inp_zip.read(relative_file_path)
                with open(dest_file, "wb") as outp:
                    outp.write(content)

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


def _print_execution_results(exec_results, goal, error_occurred: bool):
    coverage = exec_results.coverage_total
    print("---Results---")
    print("Tests run:", len(exec_results.results))
    if not coverage:
        print("No coverage information available")
    else:
        print("Coverage: {}%".format(coverage.hits_percent))
        print("Number of goals: {}".format(coverage.count_total))

    if goal != eu.COVER_ERRORS:
        verdict = VERDICT_DONE
    else:
        if any(r == eu.COVERS for r in exec_results.results):
            verdict = VERDICT_TRUE
        else:
            verdict = VERDICT_UNKNOWN
    if error_occurred:
        if verdict == VERDICT_TRUE:
            verdict = VERDICT_ERROR + " ({})".format(verdict)
        else:
            verdict = VERDICT_ERROR
    print("Result:", verdict)


def _write_execution_results(output_file, exec_results) -> None:
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    if os.path.exists(output_file):
        os.remove(output_file)

    test_coverages = exec_results.coverage_tests
    coverage_sequence = exec_results.coverage_sequence
    reduced_test_coverages = exec_results.reduced_coverage_tests
    header = list()
    data = list()
    if test_coverages:
        header += [CSV_HEADER_TEST, CSV_HEADER_COVERAGE_INDIVIDUAL]
        data.append([tc.test_vectors_as_string() for tc in test_coverages])
        data.append([tc.hits_percent for tc in test_coverages])
    if coverage_sequence:
        header.append(CSV_HEADER_COVERAGE_SEQUENCE)
        data.append(coverage_sequence)
    if reduced_test_coverages:
        header.append(CSV_HEADER_COVERAGE_REDUCED)
        assert (
            test_coverages
        ), "Reduced test coverage can only be used with individual test coverage"
        test_names = [tc.test_vectors_as_string() for tc in test_coverages]
        reduced_tests = [tc.test_vectors_as_string() for tc in reduced_test_coverages]
        data.append(["x" if test in reduced_tests else "o" for test in test_names])

    header += [
        CSV_HEADER_RESULT,
        CSV_HEADER_RETURNCODE,
        CSV_HEADER_CPUTIME,
        CSV_HEADER_WALLTIME,
    ]
    data.append(
        ["o" if r.execution_info.got_aborted else "x" for r in exec_results.results]
    )
    data.append([r.execution_info.returncode for r in exec_results.results])
    data.append([r.execution_info.cpu_time if r.execution_info.cpu_time else '' for r in exec_results.results])
    data.append([r.execution_info.wall_time if r.execution_info.wall_time else '' for r in exec_results.results])

    table = np.array(data)
    with open(output_file, mode="w") as individual_test_cov_file:
        writer = csv.writer(
            individual_test_cov_file, delimiter=DELIMITER_TEST_COVERAGES
        )
        writer.writerow(header)
        for table_column in table.T:
            writer.writerow(table_column)


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
    reduce_tests = args.reduce_tests

    error_occurred = False
    try:
        executor = execution.SuiteExecutor(
            args.goal,
            args.timelimit_per_run,
            compute_sequence=args.print_seq,
            reduce_tests=reduce_tests,
            harness_file_target=harness_file,
            compile_target=executable,
            compute_individuals=compute_individuals,
            memlimit=args.memlimit,
            cores=args.cpu_cores,
            use_runexec=args.use_runexec,
            isolate_tests=args.use_isolation,
            info_output=True,
        )

        executor.run(args.file, args.test_suite, args.machine_model, exec_results)

        if not exec_results.results:
            logging.warning(
                "No test case in exchange format found in '%s'", args.test_suite
            )

    except FileNotFoundError as e:
        logging.error(e)
        error_occurred = True
    except execution.ExecutionError as e:
        logging.error(e.msg)
        error_occurred = True
    finally:
        if exec_results.successful_tests:
            _write_tests_to_suite(
                args.file,
                args.test_suite,
                exec_results.successful_tests,
                args.goal,
                os.path.join(args.output_dir, args.reduced_suite_name),
            )
            if args.check_for_error:
                # If at least one test covered an error,
                # make the first one into an executable harness
                _write_harness(
                    args.file, exec_results.successful_tests[0], args.output_dir
                )

        _write_execution_results(
            os.path.join(args.output_dir, RESULTS_FILE), exec_results
        )
        if args.write_plots and exec_results.coverage_total:
            try:
                from suite_validation import plotting

                plotting.create_plots(exec_results, args.goal, args.output_dir)
            except ImportError as e:
                logging.warning("Not plotting coverage statistics: %s", e.msg)

        print()
        _print_execution_results(exec_results, args.goal, error_occurred)
