# testcov is a tool for validation and execution of test suites.
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
import logging
import os
import re
from typing import Tuple
from suite_validation import execution
from suite_validation import execution_utils as eu
from suite_validation import reduction_strategy as rs
from suite_validation import writer as suite_writer
from suite_validation import _tool_info

RESULTS_NAME = "results"
REDUCED_TESTSUITE_NAME = "reduced-suite.zip"

VERDICT_DONE = "DONE"
VERDICT_UNKNOWN = "UNKNOWN"
VERDICT_TRUE = "TRUE"
VERDICT_ERROR = "ERROR"


class IllegalArgumentError(Exception):
    pass


def get_parser():
    parser = argparse.ArgumentParser(
        prog=_tool_info.__NAME__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--version", "-v", action="version", version=_tool_info.__VERSION__
    )

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
        "--results-format",
        dest="results_format",
        action="store",
        default="json",
        help="Format to use for writing individual results. Possible options: csv, json",
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


def _decide_execution_result(exec_results, goal, error_occurred: bool) -> Tuple[str, int]:
    """ Checks test-execution results and prepares the results string/return code."""
    results_output = ["---Results---", "Tests run: {}".format(len(exec_results.results))]
    coverage = exec_results.coverage_total
    if not coverage:
        results_output.append("No coverage information available")
    else:
        results_output.append("Coverage: {}%".format(coverage.hits_percent))
        results_output.append("Number of goals: {}".format(coverage.count_total))

    if goal != eu.COVER_ERRORS:
        if any(r == eu.ABORTED for r in exec_results.results):
            verdict = VERDICT_UNKNOWN
            return_code = 1
        else:
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
    results_output.append("Result: {}".format(verdict))
    results_str = "\n".join(results_output)

    if verdict not in (VERDICT_DONE, VERDICT_TRUE):
        return_code = 1
    else:
        return_code = 0
    return results_str, return_code


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
    return_code = None
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
            suite_writer.write_tests_to_suite(
                args.file,
                args.test_suite,
                exec_results.successful_tests,
                args.goal,
                os.path.join(args.output_dir, args.reduced_suite_name),
            )
            if args.check_for_error:
                # If at least one test covered an error,
                # make the first one into an executable harness
                suite_writer.write_harness(
                    args.file, exec_results.successful_tests[0], args.output_dir
                )

        results_file_name = RESULTS_NAME + "." + args.results_format
        suite_writer.write_results(
            os.path.join(args.output_dir, results_file_name),
            exec_results,
            args.results_format,
        )
        if args.write_plots and exec_results.coverage_total:
            try:
                from suite_validation import plotting

                plotting.create_plots(exec_results, args.goal, args.output_dir)
            except ImportError as e:
                logging.warning("Not plotting coverage statistics: %s", e.msg)

        results_str, return_code = _decide_execution_result(exec_results, args.goal, error_occurred)
        print()
        print(results_str)
    return return_code
