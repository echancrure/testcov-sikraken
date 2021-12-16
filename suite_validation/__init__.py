# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Main module of testcov."""

import argparse
import os
import re
import sys
import zipfile
from typing import Tuple
from suite_validation import execution
from suite_validation import execution_utils as eu
from suite_validation import reduction_strategy as rs
from suite_validation import writer as suite_writer
from suite_validation import _tool_info
from suite_validation import _logger as logging

RESULTS_NAME = "results"
REDUCED_TESTSUITE_NAME = "reduced-suite.zip"

VERDICT_DONE = "DONE"
VERDICT_UNKNOWN = "UNKNOWN"
VERDICT_TRUE = "TRUE"
VERDICT_ERROR = "ERROR"


class IllegalArgumentError(Exception):
    pass


class StorePath(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs, **kwargs)

    @staticmethod
    def create_path(path) -> str:
        return path

    def __call__(self, parser, namespace, values, option_string=None):
        del parser, option_string
        paths = None
        if values is not None:
            if isinstance(values, str):
                paths = self.create_path(values)
            else:
                paths = [self.create_path(v) for v in values]
        setattr(namespace, self.dest, paths)


class StoreInputPath(StorePath):
    @staticmethod
    def create_path(path) -> str:
        if not os.path.exists(path):
            raise ValueError(f"Given path {path} does not exist")
        return path


def get_parser():
    parser = argparse.ArgumentParser(
        prog=_tool_info.__NAME__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--version", "-v", action="version", version=_tool_info.__VERSION__
    )

    parser.add_argument(
        "--use-gcov",
        dest="use_gcov",
        action="store_true",
        default=False,
        help="Use GCov measurement instead of lcov. This only gives an overall coverage and no individual results, but may be faster.",
    )

    parser.add_argument(
        "--goal",
        dest="goal_file",
        action=StoreInputPath,
        required=False,
        help="File that defines coverage goal to measure. The default goal is branch coverage.",
    )

    parser.add_argument(
        "--no-stop-on-success",
        dest="stop_on_success",
        action="store_false",
        default=True,
        help="Do not stop early if goal is cover-error and an error-call is found. This argument will always execute the full test suite (within the set limits)",
    )

    parser.add_argument(
        "--test-suite",
        dest="test_suite",
        action=StoreInputPath,
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
        action=StorePath,
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
        choices=rs.REDUCTION_STRATEGIES.keys(),
        help="apply reduction strategy to create a reduced test suite.",
        required=False,
    )

    parser.add_argument(
        "--reduction-output",
        dest="reduced_suite_name",
        action=StorePath,
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

    parser.add_argument("file", action=StoreInputPath, help="program file")

    return parser


def parse(argv):
    parser = get_parser()
    args = parser.parse_args(argv)

    if not args.goal_file:
        args.goal = eu.COVER_BRANCHES
    else:
        args.goal = parse_coverage_goal_file(args.goal_file)
    args.check_for_error = isinstance(args.goal, eu.CoverFunc)
    args.use_runexec = args.use_runexec and args.use_isolation

    if args.use_gcov:
        args.individual_test_cov = False
        args.reduce_tests = False
        args.write_plots = False
        args.use_isolation = False
        args.use_runexec = False

    return args


def parse_coverage_goal_file(goal_file: str) -> str:
    with open(goal_file, encoding="UTF-8") as inp:
        content = inp.read().strip()
    prop_match = re.match(
        r"COVER\s*\(\s*init\s*\(\s*main\s*\(\s*\)\s*\)\s*,\s*FQL\s*\(COVER\s+EDGES\s*\((.*)\)\s*\)\s*\)",
        content,
    )
    if not prop_match:
        raise IllegalArgumentError(
            f"No valid coverage goal specification in file {goal_file}: {content[:100]}"
        )

    goal = prop_match.group(1).strip()
    if goal not in eu.COVERAGE_GOALS:
        raise IllegalArgumentError(f"No valid coverage goal specification: {goal}")
    return eu.COVERAGE_GOALS[goal]


def _decide_execution_result(
    exec_results, goal, error_occurred: bool
) -> Tuple[str, int]:
    """Checks test-execution results and prepares the results string/return code."""
    results_output = [
        "---Results---",
        f"Tests run: {len(exec_results.results)}",
        f"Tests in suite: {len(exec_results.all_tests)}",
    ]
    coverage = exec_results.coverage_total
    if not coverage or coverage.count_total is None:
        results_output.append("No coverage information available")
    else:
        results_output.append(f"Coverage: {coverage.hits_percent}%")
        results_output.append(f"Number of goals: {coverage.count_total}")

    if not isinstance(goal, eu.CoverFunc):
        if any(r == eu.ABORTED for r in exec_results.results):
            verdict = VERDICT_UNKNOWN
        else:
            verdict = VERDICT_DONE
    else:
        if any(r == eu.COVERS for r in exec_results.results):
            verdict = VERDICT_TRUE
        else:
            verdict = VERDICT_UNKNOWN
    if error_occurred:
        if verdict == VERDICT_TRUE:
            verdict = VERDICT_ERROR + f" ({verdict})"
        else:
            verdict = VERDICT_ERROR
    results_output.append(f"Result: {verdict}")
    results_str = "\n".join(results_output)

    if verdict.startswith(VERDICT_ERROR):
        return_code = 1
    else:
        return_code = 0
    return results_str, return_code


def reduce_testsuite(execution_results, reduction_strategy) -> None:
    """
    Creates a reduced test suite for the given execution results, insitu.
    Puts the reduced test suite into execution_results.reduced_coverage_tests.
    Also replaces the set of successful tests with this reduced suite.
    """
    if not (
        execution_results.coverage_tests
        and execution_results.coverage_total
        and any(c.coverage for c in execution_results.coverage_tests)
    ):
        logging.debug("Can't reduce test suite because of missing coverage information")
        return
    execution_results.reduced_coverage_tests = rs.execute(
        reduction_strategy, execution_results.coverage_tests[:]
    )
    execution_results.successful_tests = [
        tvec
        for tcov in execution_results.reduced_coverage_tests
        for tvec in tcov.test_vectors
    ]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse(argv)

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    logfile = os.path.join(args.output_dir, "testcov.log")
    if args.verbose:
        logging.init(logging.DEBUG, logfile=logfile)
    else:
        logging.init(logging.INFO, logfile=logfile)

    exec_results = eu.SuiteExecutionResult()
    harness_file = os.path.join(args.output_dir, "harness.c")
    executable = os.path.join(args.output_dir, "a.out")
    compute_individuals = args.individual_test_cov

    error_occurred = True  # set to False in try-else
    try:
        try:
            executor = execution.SuiteExecutor(
                args.goal,
                args.timelimit_per_run,
                harness_file_target=harness_file,
                compile_target=executable,
                compute_individuals=compute_individuals,
                memlimit=args.memlimit,
                cores=args.cpu_cores,
                use_runexec=args.use_runexec,
                use_gcov_only=args.use_gcov,
                isolate_tests=args.use_isolation,
                info_output=True,
                stop_on_success=args.stop_on_success,
            )

            executor.run(args.file, args.test_suite, args.machine_model, exec_results)
            if not exec_results.results:
                logging.warning(
                    "No test case in exchange format found in '%s'", args.test_suite
                )
            else:
                # Post-processing of test data
                reduce_testsuite(exec_results, args.reduce_tests)

        except FileNotFoundError as e:
            logging.error(e)
        except (IsADirectoryError, zipfile.BadZipFile) as e:
            logging.error(e)
            logging.info(
                "Test suites are expected as ZIP files. Try to zip the test-suite directory and provide the result as test suite"
            )
        except execution.ExecutionError as e:
            logging.error(e.msg)
        except KeyboardInterrupt:
            logging.info("Execution interrupted by user")
        else:
            error_occurred = False
        finally:
            # Output data
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
    except KeyboardInterrupt:
        logging.info("Execution interrupted by user")
    finally:
        results_str, return_code = _decide_execution_result(
            exec_results, args.goal, error_occurred
        )
        print()
        print(results_str)
    return return_code
