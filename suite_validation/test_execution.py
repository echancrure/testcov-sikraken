# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020 Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for execution module."""

import os
import subprocess
import tempfile
import itertools
import suite_validation.coverage as cov
import suite_validation.reduction_strategy as rs
import suite_validation.execution as ex
import suite_validation.execution_utils as eu
import suite_validation

MODULE_DIRECTORY = os.path.join(
    os.path.dirname(suite_validation.__file__), os.path.pardir
)

COVER_REACH = eu.CoverFunc("reach_error")

TEST_DIRECTORY = os.path.join(MODULE_DIRECTORY, "test")
TEST_FILE_WITHOUT_ERR = os.path.join(TEST_DIRECTORY, "test.c")
TEST_FILES_WITH_ERR = [
    (os.path.join(TEST_DIRECTORY, f), v)
    for f, v in (
        ("test_false_VerifierError.c", eu.CoverFunc("__VERIFIER_error")),
        ("test_false_ReachError.c", COVER_REACH),
        ("test_false_ReachError-malloc-defined.c", COVER_REACH),
        ("test_false_ReachErrorMultiline.c", COVER_REACH),
        ("test_ifWithoutBraces_ReachError.c", COVER_REACH),
        ("test_ternary_ReachError.c", COVER_REACH),
        ("test_while_ReachError.c", COVER_REACH),
        ("test_switch_ReachError.c", COVER_REACH),
        ("test_required_declarations.c", COVER_REACH),
        ("test_assume_block.c", COVER_REACH),
        ("test_assume_singleline.c", COVER_REACH),
    )
]
TEST_FILE_WITH_NO_TERMINATION = os.path.join(TEST_DIRECTORY, "test_no-termination.c")
TEST_FILE_WITH_STRINGS = os.path.join(TEST_DIRECTORY, "test_string.c")
TEST_FILE_COVERAGE = os.path.join(TEST_DIRECTORY, "test_coverages.c")
TEST_FILE_SIMPLE_IF = os.path.join(TEST_DIRECTORY, "test_simple-if.c")
TEST_FILE_NO_INPUTS = os.path.join(TEST_DIRECTORY, "test_no_inputs.c")
TEST_FILE_ABORTS = os.path.join(TEST_DIRECTORY, "test_abort.c")
TEST_FILE_ASSERT_FAIL = os.path.join(TEST_DIRECTORY, "test_assertFail.c")

TEST_HARNESS = os.path.join(TEST_DIRECTORY, "test_harness.c")

SUITE_DIR = os.path.join(TEST_DIRECTORY, "suites")
SUITE_VALID_ZIP = os.path.join(SUITE_DIR, "suite-valid.zip")
SUITE_VALID_NESTED_ZIP = os.path.join(SUITE_DIR, "suite-valid-nested.zip")
SUITE_VALID_STRINGS = os.path.join(SUITE_DIR, "suite-string.zip")
SUITE_INVALID_ZIP = os.path.join(SUITE_DIR, "suite-metadata-missing.zip")
SUITE_COVERAGE = os.path.join(SUITE_DIR, "suite-coverages.zip")
SUITE_SIMPLE_IF = os.path.join(SUITE_DIR, "suite-simple-if.zip")
SUITE_SIMPLE_IF_SWAPPED = os.path.join(SUITE_DIR, "suite-simple-if-swapped.zip")
SUITE_EMPTY_TESTCASE = os.path.join(SUITE_DIR, "suite-empty-test.zip")
SUITE_ABORTS = os.path.join(SUITE_DIR, "suite-abort.zip")
SUITE_ASSERT_FAIL = os.path.join(SUITE_DIR, "suite-assert_fail.zip")

MACHINE_MODELS = (eu.MACHINE_MODEL_32, eu.MACHINE_MODEL_64)

DUMMY_FILE = "DUMMY_FILE"
DUMMY_TEST_VECTOR_RESULT = {eu.TestVector("dummy_tv", "dummy.xml"): eu.UNKNOWN}


# pylint: disable=protected-access
class TestHarness:
    """Tests for harness creation with ex.HarnessCreator."""

    def test_harness_without_test_vector_compilable(self, tmp_path):
        with WorkIn(tmp_path):
            self._check_compilable()

    def test_harness_with_test_vector_compilable(self, tmp_path):
        vectors = []

        test_vector = eu.TestVector("int_input", "dummy.xml")
        test_vector.add("0")
        vectors.append(test_vector)

        test_vector = eu.TestVector("int_input_with_method", "dummy.xml")
        test_vector.add("0", method="__VERIFIER_nondet_int")
        vectors.append(test_vector)

        test_vector = eu.TestVector("char_input", "dummy.xml")
        test_vector.add("'a'")
        vectors.append(test_vector)

        test_vector = eu.TestVector("hex_input", "dummy.xml")
        test_vector.add("0x0000f")
        vectors.append(test_vector)

        test_vector = eu.TestVector("multiple_inputs", "dummy.xml")
        test_vector.add("0")
        test_vector.add("5")
        test_vector.add("999")
        vectors.append(test_vector)

        test_vector = eu.TestVector("string_inputs", "dummy.xml")
        test_vector.add('"Some string value"')
        vectors.append(test_vector)

        test_vector = eu.TestVector("multiple_input_types", "dummy.xml")
        test_vector.add("0")
        test_vector.add("'b'")
        test_vector.add("0xff000f9a")
        vectors.append(test_vector)

        for tv in vectors:
            with WorkIn(tmp_path):
                self._check_compilable(tv)

    @staticmethod
    def _check_compilable(test_vector=None):
        compile_cmd = [
            "gcc",
            "-Wno-attributes",
            "-x",
            "c",
            "-include",
            TEST_FILE_WITHOUT_ERR,
            "-",
        ]

        harness = ex.HarnessCreator().convert(TEST_FILE_WITHOUT_ERR, test_vector)

        with subprocess.Popen(compile_cmd, stdin=subprocess.PIPE) as compile_exec:
            compile_exec.communicate(harness.encode())
            returncode = compile_exec.poll()

        assert returncode == 0, f"Compilation failed: {compile_cmd}"


# pylint: disable=protected-access
class TestExecutionRunner:
    """Tests for ex.ExecutionRunner."""

    @staticmethod
    def get_runner(machine_model, timelimit, goal=None):
        del goal
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.ExecutionRunner(
            machine_model, timelimit, harness_file, compile_output_file
        )

    def test_harness_creation(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_harness_creation(machine_model)

    def _check_harness_creation(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)

        try:
            output_file = runner.get_executable_harness(TEST_FILE_WITHOUT_ERR)
        except ex.ExecutionError as e:
            assert False, f"Harness creation failed: {e}"

        assert os.path.exists(output_file), f"Harness {output_file} not found"

    def test_harness_compile(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_harness_creation(machine_model)

    def _check_harness_compile(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        try:
            out_file = runner.compile(TEST_FILE_WITHOUT_ERR, TEST_HARNESS, out_file)
        except ex.ExecutionError as e:
            assert False, f"Compilation failed: {e}"

        assert os.path.exists(out_file)

    def test_invalid_harness_compile_throws_error(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_invalid_harness_compile_throws_error(machine_model)

    def _check_invalid_harness_compile_throws_error(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        try:
            runner.compile(TEST_FILE_WITHOUT_ERR, "harness.c", out_file)
        except ex.ExecutionError:
            pass
        else:
            assert False, "Expected ExecutionError"

    def test_invalid_program_compile_throws_error(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_invalid_harness_compile_throws_error(machine_model)

    def _check_invalid_program_compile_throws_error(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        try:
            runner.compile("program.c", TEST_HARNESS, out_file)
        except ex.ExecutionError:
            pass
        else:
            assert False, "Expected ExecutionError"

    def test_execution_run_result_unknown(self, tmp_path):
        simple_vector = eu.TestVector("dummy", "dummy.xml")
        simple_vector.add("1")

        for machine_model in MACHINE_MODELS:
            for timelimit in (None, 5, 10, 99999):
                with WorkIn(tmp_path):
                    self._check_test_execution_runs(
                        machine_model,
                        timelimit,
                        TEST_FILE_WITHOUT_ERR,
                        simple_vector,
                        eu.UNKNOWN,
                    )

    def _check_test_execution_runs(
        self, machine_model, timelimit, test_file, test_vector, expected
    ):
        runner = self.get_runner(machine_model, timelimit)

        run_result = runner.run(test_file, test_vector)

        assert run_result == expected

    def test_execution_run_non_terminating_with_timelimit(self, tmp_path):
        empty_vector = eu.TestVector("dummy", "dummy.xml")
        timelimit = 3

        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_test_execution_runs(
                    machine_model,
                    timelimit,
                    TEST_FILE_WITH_NO_TERMINATION,
                    empty_vector,
                    eu.ABORTED,
                )


class TestCoverageMeasuringExecutionRunner(TestExecutionRunner):
    """Tests for ex.CoverageMeasuringExecutionRunner."""

    @staticmethod
    def get_runner(machine_model, timelimit, goal=eu.COVER_BRANCHES):
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.LcovCoverageMeasurer(
            machine_model,
            timelimit,
            goal,
            harness_file,
            compile_output_file,
            individual_runs=False,
        )

    def test_get_line_coverage_single_execution(self, tmp_path):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_line_coverage_multiple_executions(
                    machine_model, [vector_going_one_way]
                )

    def test_get_condition_coverage_single_execution(self, tmp_path):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_condition_coverage_multiple_executions(
                    machine_model, [vector_going_one_way]
                )

    def test_get_line_coverage_multiple_executions(self, tmp_path):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        vector_going_other_way = eu.TestVector("vector2", "vector2.xml")
        vector_going_other_way.add("-5")

        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_line_coverage_multiple_executions(
                    machine_model, [vector_going_one_way, vector_going_other_way]
                )

    def test_get_condition_coverage_multiple_executions(self, tmp_path):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        vector_going_other_way = eu.TestVector("vector2", "vector2.xml")
        vector_going_other_way.add("-5")

        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_condition_coverage_multiple_executions(
                    machine_model,
                    [
                        vector_going_one_way,
                        vector_going_other_way,
                    ],
                )

    def _check_line_coverage_multiple_executions(self, machine_model, vectors):
        goal = eu.COVER_LINES
        runner = self.get_runner(machine_model, None, goal)
        test_file = TEST_FILE_WITHOUT_ERR

        old_line_cov = 0
        for tv in vectors:
            result = runner.run(test_file, tv)
            coverage = result.coverage

            assert coverage.hits > 0, "Line coverage at 0"
            assert (
                coverage.hits > old_line_cov
            ), f"Line coverage didn't increase: {coverage.hits}"

            old_line_cov = coverage.hits

    def _check_condition_coverage_multiple_executions(self, machine_model, vectors):
        goal = eu.COVER_CONDITIONS
        runner = self.get_runner(machine_model, None, goal)
        test_file = TEST_FILE_WITHOUT_ERR

        old_condition_cov = 0
        for tv in vectors:
            result = runner.run(test_file, tv)
            coverage = result.coverage

            assert coverage.hits > 0, "Condition coverage at 0"
            assert (
                coverage.hits > old_condition_cov
            ), f"Condition coverage didn't increase: {coverage.hits}"

            old_condition_cov = coverage.hits

    def test_function_call_coverage(self, tmp_path):
        covering_vector = eu.TestVector("covers_test", "covers_test.c")
        covering_vector.add("'a'")
        covering_vector.add("5")
        covering_vector.add("0x10")

        missing_vector = eu.TestVector("misses_test", "misses_test.c")
        missing_vector.add("'z'")
        missing_vector.add("5")
        missing_vector.add("0x0f")

        for machine_model in MACHINE_MODELS:
            for err_file, goal in TEST_FILES_WITH_ERR:
                with WorkIn(tmp_path):
                    self._check_call_coverage(
                        machine_model, err_file, goal, covering_vector, eu.COVERS
                    )

        for machine_model in MACHINE_MODELS:
            for err_file, goal in TEST_FILES_WITH_ERR:
                with WorkIn(tmp_path):
                    self._check_call_coverage(
                        machine_model, err_file, goal, missing_vector, eu.UNKNOWN
                    )

    def test_function_call_coverage_incomplete_input(self, tmp_path):
        runner = self.get_runner(eu.MACHINE_MODEL_32, None, COVER_REACH)
        err_file = os.path.join(TEST_DIRECTORY, "test_multiple_branches_ReachError.c")

        incomplete_vector = eu.TestVector("incomplete input", "incomplete_input.c")
        incomplete_vector.add("'a'")
        incomplete_vector.add("5")
        incomplete_vector.add("0x10")
        # file #test_multiple_branches_ReachError requires four inputs, so this vector is missing one (on purpose)
        # let's see what happens.

        with WorkIn(tmp_path):
            run_result = runner.run(err_file, incomplete_vector)

        assert run_result == eu.UNKNOWN

    def test_function_call_coverage_complete_input_if_without_braces(self, tmp_path):
        runner = self.get_runner(eu.MACHINE_MODEL_32, None, COVER_REACH)
        err_file = os.path.join(TEST_DIRECTORY, "test_ifWithoutBraces_ReachError.c")

        incomplete_vector = eu.TestVector("incomplete input", "incomplete_input.c")
        incomplete_vector.add("'a'")
        incomplete_vector.add("5")
        incomplete_vector.add("0x10")
        incomplete_vector.add("0x10")
        # file #test_multiple_branches_ReachError requires four inputs, so this vector is complete

        with WorkIn(tmp_path):
            run_result = runner.run(err_file, incomplete_vector)

        assert run_result == eu.COVERS

    def _check_call_coverage(self, machine_model, test_file, goal, vector, expected):
        runner = self.get_runner(machine_model, None, goal)

        run_result = runner.run(test_file, vector)

        assert run_result == expected


class WorkIn:
    def __init__(self, workdir):
        self._old_dir = None
        self._tmp_dir = workdir

    def __enter__(self):
        self._old_dir = os.getcwd()
        os.chdir(self._tmp_dir)

    def __exit__(self, t, value, traceback):
        os.chdir(self._old_dir)


# pylint: disable=protected-access
class TestSuiteExecutor:
    """Tests for ex.SuiteExecutor."""

    PROGRAM_FILE_WITH_ERR = TEST_FILES_WITH_ERR[-1][0]

    @staticmethod
    def get_runner(
        goal=eu.COVER_BRANCHES,
        timelimit=None,
        compute_individuals=True,
    ):
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.SuiteExecutor(
            goal,
            timelimit,
            harness_file,
            compile_output_file,
            isolate_tests=False,
            compute_individuals=compute_individuals,
            use_runexec=False,
        )

    def test_empty_testcase(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_empty(machine_model)

    def _check_run_suite_empty(self, machine_model):
        runner = self.get_runner()

        result_obj = runner.run(
            TEST_FILE_NO_INPUTS, SUITE_EMPTY_TESTCASE, machine_model
        )
        found_tests = result_obj.all_tests
        results = result_obj.results
        branches = result_obj.coverage_total.coverage

        assert (
            len(found_tests) == 1
        ), f"Did not find exactly one test, but {len(found_tests)}"
        assert len(results) == 1, "Empty testcase not executed"
        assert branches, "Coverage information invalid: {branches}"

    def test_run_suite_valid(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_valid(machine_model, SUITE_VALID_ZIP)

    def test_run_nested_suite_valid(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_valid(machine_model, SUITE_VALID_NESTED_ZIP)

    def _check_run_suite_valid(self, machine_model, suite_location):
        runner = self.get_runner(goal=COVER_REACH)

        result_obj = runner.run(
            TestSuiteExecutor.PROGRAM_FILE_WITH_ERR, suite_location, machine_model
        )
        found_tests = result_obj.all_tests
        results = result_obj.results
        branches = result_obj.coverage_total.coverage

        assert (
            len(found_tests) == 2
        ), f"Did not find exactly two tests, but {len(found_tests)}"
        assert len(results) == 2, "Not both tests executed"
        assert (
            results.count(eu.COVERS) == 1 and results.count(eu.UNKNOWN) == 1
        ), f"Expected exactly one result to be {eu.COVERS} and one to be {eu.UNKNOWN}: {results}"
        assert branches, f"Coverage information invalid: {branches}"

    @staticmethod
    def _check_file_exists(filename):
        assert os.path.exists(filename), f"File doesn't exist: {filename}"

    def test_run_suite_without_metadata_throws_error(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_without_metadata_throws_error(
                    machine_model, SUITE_INVALID_ZIP
                )

    def _check_run_suite_without_metadata_throws_error(
        self, machine_model, suite_location
    ):
        runner = self.get_runner()

        try:
            runner.run(
                TestSuiteExecutor.PROGRAM_FILE_WITH_ERR, suite_location, machine_model
            )
        except ex.ExecutionError:
            pass
        else:
            assert False, "Expected ExecutionError"

    def test_run_suite_with_non_terminating_program(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_with_non_terminating_program(
                    machine_model, SUITE_VALID_ZIP
                )

    def _check_run_suite_with_non_terminating_program(
        self, machine_model, suite_location
    ):
        runner = self.get_runner(timelimit=2)

        result_obj = runner.run(
            TEST_FILE_WITH_NO_TERMINATION, suite_location, machine_model
        )
        found_tests = result_obj.all_tests
        results = result_obj.results

        assert (
            len(found_tests) == 2
        ), f"Did not find exactly two tests, but {len(found_tests)}"
        assert len(results) == 2 and all(
            r == eu.ABORTED for r in results
        ), f"Expected two results '{eu.ABORTED}': {results}"

    def test_run_suite_with_string_inputs(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            with WorkIn(tmp_path):
                self._check_run_suite_with_string_inputs(
                    machine_model, SUITE_VALID_STRINGS
                )

    def _check_run_suite_with_string_inputs(self, machine_model, suite_location):
        runner = self.get_runner(goal=COVER_REACH, timelimit=2)

        result_obj = runner.run(TEST_FILE_WITH_STRINGS, suite_location, machine_model)
        found_tests = result_obj.all_tests
        results = result_obj.results

        assert (
            len(found_tests) == 2
        ), f"Did not find exactly two tests, but {len(found_tests)}"
        assert (
            len(results) == 2
            and any(r == eu.COVERS for r in results)
            and any(r == eu.UNKNOWN for r in results)
        ), f"Expected results '{eu.COVERS}' and '{eu.UNKNOWN}', but got: {results}"

    def test_compute_individuals_produces_same_coverage(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            for goal in eu.COVERAGE_GOALS.values():
                runners = [
                    self.get_runner(goal),
                    self.get_runner(goal, compute_individuals=False),
                    self.get_runner(goal, compute_individuals=False),
                ]
                runners_tuples = itertools.combinations(runners, 2)

                for runner1, runner2 in runners_tuples:
                    with WorkIn(tmp_path):
                        self._check_coverage_results_equal(
                            runner1, runner2, SUITE_VALID_ZIP, machine_model
                        )

    @staticmethod
    def _get_config_str(runner):
        # pylint: disable=protected-access
        return f"SuiteExecutor[ComputeInd={runner._compute_individual_test_coverages}]"

    def _check_coverage_results_equal(
        self, runner1, runner2, suite_location, machine_model
    ):
        result_obj = runner1.run(
            TestSuiteExecutor.PROGRAM_FILE_WITH_ERR, suite_location, machine_model
        )
        coverage1 = result_obj.coverage_total.hits

        result_obj = runner2.run(
            TestSuiteExecutor.PROGRAM_FILE_WITH_ERR, suite_location, machine_model
        )
        coverage2 = result_obj.coverage_total.hits

        config1 = self._get_config_str(runner1)
        config2 = self._get_config_str(runner2)
        err_msg = f"Unequal for {config1} and {config2}"

        assert coverage1 == coverage2, err_msg + f": {coverage1} vs {coverage2}"

    def test_line_coverage_correct(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_LINES)
            with WorkIn(tmp_path):
                self._check_line_coverage(runner, machine_model)

    def test_branch_coverage_correct(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_BRANCHES)
            with WorkIn(tmp_path):
                self._check_branch_coverage(runner, machine_model)

    def test_branch_coverage_correct_with_aborts_in_program(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_BRANCHES)
            with WorkIn(tmp_path):
                result_obj = runner.run(TEST_FILE_ABORTS, SUITE_ABORTS, machine_model)
                test_coverage = result_obj.coverage_total

                assert test_coverage.hits == 6
                assert test_coverage.hits_percent == 100
                assert test_coverage.count_total == 6

    def test_branch_coverage_correct_with_assert_fail_in_program(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_BRANCHES)
            with WorkIn(tmp_path):
                result_obj = runner.run(
                    TEST_FILE_ASSERT_FAIL, SUITE_ASSERT_FAIL, machine_model
                )
                test_coverage = result_obj.coverage_total

                assert test_coverage.hits == 12
                assert test_coverage.hits_percent == 100
                assert test_coverage.count_total == 12

    def test_function_call_coverage_correct_with_assert_fail_in_program(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(COVER_REACH)
            with WorkIn(tmp_path):
                result_obj = runner.run(
                    TEST_FILE_ASSERT_FAIL, SUITE_ASSERT_FAIL, machine_model
                )
                test_coverage = result_obj.coverage_total

                assert test_coverage.hits == 1
                assert test_coverage.hits_percent == 100
                assert test_coverage.count_total == 1

    def test_condition_coverage_correct(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_CONDITIONS)
            with WorkIn(tmp_path):
                self._check_condition_coverage(runner, machine_model)

    @staticmethod
    def _check_line_coverage(runner, machine_model):
        result_obj = runner.run(TEST_FILE_COVERAGE, SUITE_COVERAGE, machine_model)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits == 9
        assert test_coverage.hits_percent == 75.0
        assert test_coverage.count_total == 12

    @staticmethod
    def _check_branch_coverage(runner, machine_model):
        result_obj = runner.run(TEST_FILE_COVERAGE, SUITE_COVERAGE, machine_model)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits == 4
        assert test_coverage.hits_percent == 50
        assert test_coverage.count_total == 8

    @staticmethod
    def _check_condition_coverage(runner, machine_model):
        result_obj = runner.run(TEST_FILE_COVERAGE, SUITE_COVERAGE, machine_model)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits == 4
        assert test_coverage.hits_percent == 33.33
        assert test_coverage.count_total == 12

    def test_reduction_correct(self, tmp_path):
        strategies = [rs.BYORDER_REDUCTION, rs.FURTHEST_DIFF_REDUCTION]
        for machine_model in MACHINE_MODELS:
            for goal in eu.COVERAGE_GOALS.values():
                runner = self.get_runner(goal)
                for strategy in strategies:
                    with WorkIn(tmp_path):
                        self._check_reduction_correct_suite_simple_if(
                            runner, strategy, machine_model, goal
                        )
                        self._check_reduction_correct_suite_simple_if_inverted(
                            runner, strategy, machine_model, goal
                        )

    # pylint: disable=invalid-name
    def test_function_call_coverage_xcsp_AllInterval013(self, tmp_path):
        program = os.path.join(TEST_DIRECTORY, "AllInterval-013.c")
        test_suite = os.path.join(SUITE_DIR, "suite-xcsp-AllInterval-013.zip")
        runner = self.get_runner(COVER_REACH)

        with WorkIn(tmp_path):
            result_obj = runner.run(program, test_suite, eu.MACHINE_MODEL_32)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits_percent == 100

    def test_function_call_coverage_heap_sll_to_dll_rev1(self, tmp_path):
        program = os.path.join(TEST_DIRECTORY, "sll_to_dll_rev-1.i")
        # we use this test suite on purpose: it finds the function call
        test_suite = os.path.join(SUITE_DIR, "suite-xcsp-AllInterval-013.zip")
        runner = self.get_runner(COVER_REACH)

        with WorkIn(tmp_path):
            result_obj = runner.run(program, test_suite, eu.MACHINE_MODEL_32)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits_percent == 100

    def test_branch_coverage_high_nesting_level(self, tmp_path):
        program = os.path.join(TEST_DIRECTORY, "id_build.i.p+sep-reducer.c")
        test_suite = os.path.join(SUITE_DIR, "suite-id_build-hybridtiger.zip")
        runner = self.get_runner(eu.COVER_BRANCHES)

        with WorkIn(tmp_path):
            result_obj = runner.run(program, test_suite, eu.MACHINE_MODEL_32)
        test_coverage = result_obj.coverage_total

        assert test_coverage.hits_percent > 0

    @staticmethod
    def _check_reduction_correct_suite_simple_if(runner, strategy, machine_model, goal):
        # the program has only one if statement (x > 0) and is fed by two different test vectors
        # the sequence of the test vectors is x:= 2, x:= -2
        result_obj: eu.SuiteExecutionResult = runner.run(
            TEST_FILE_SIMPLE_IF, SUITE_SIMPLE_IF, machine_model
        )
        suite_validation.reduce_testsuite(result_obj, strategy)
        if goal in [eu.COVER_LINES]:
            assert len(result_obj.reduced_coverage_tests) < len(
                result_obj.coverage_tests
            ), f"Inconsistent sequences: {result_obj.reduced_coverage_tests} and {result_obj.coverage_tests}"
            # only test with x = 2 included because this test executes the line in the if body and
            # gives 100% line coverage. The DIFF approach find this "better" test. The naive reduction approach
            # applies this test first.
            assert len(result_obj.reduced_coverage_tests) == 1
            total_tc_from_reduced = None
            for tc in result_obj.reduced_coverage_tests:
                assert tc in result_obj.coverage_tests
                if total_tc_from_reduced is None:
                    total_tc_from_reduced = tc
                else:
                    total_tc_from_reduced = total_tc_from_reduced + tc
            assert total_tc_from_reduced.hits_percent == 100
        if goal in [eu.COVER_BRANCHES, eu.COVER_CONDITIONS]:
            # test with x = 2 and x := -2 included because each test will give 50% branch coverage and 50%
            # condition coverage and merging this together a branch/condition coverage of 100% is obtained.
            assert len(result_obj.reduced_coverage_tests) == len(
                result_obj.coverage_tests
            ), f"Inconsistent sequences: {result_obj.reduced_coverage_tests} and {result_obj.coverage_tests}"
            assert len(result_obj.reduced_coverage_tests) == 2
            total_tc_from_reduced = None
            for tc in result_obj.reduced_coverage_tests:
                assert tc in result_obj.coverage_tests
                if total_tc_from_reduced is None:
                    total_tc_from_reduced = tc
                else:
                    total_tc_from_reduced = total_tc_from_reduced + tc
            assert total_tc_from_reduced.hits_percent == 100  # branch coverage
            assert total_tc_from_reduced.hits_percent == 100  # condition coverage

    @staticmethod
    def _check_reduction_correct_suite_simple_if_inverted(
        runner, strategy, machine_model, goal
    ):
        # the program has one if statement (x > 0) and is fed by two different test vectors
        # the sequence of the test vectors is x:=-2, x:=2
        result_obj: eu.SuiteExecutionResult = runner.run(
            TEST_FILE_SIMPLE_IF, SUITE_SIMPLE_IF_SWAPPED, machine_model
        )
        suite_validation.reduce_testsuite(result_obj, strategy)
        if goal in [eu.COVER_LINES]:
            if strategy == rs.FURTHEST_DIFF_REDUCTION:
                assert len(result_obj.reduced_coverage_tests) < len(
                    result_obj.coverage_tests
                ), f"Inconsistent sequences: {result_obj.reduced_coverage_tests} and {result_obj.coverage_tests}"
                # only test with x = 2 included because this test executes the line in the if body and
                # gives 100% line coverage. The DIFF approach finds this "better" test.
                assert len(result_obj.reduced_coverage_tests) == 1
                total_tc_from_reduced = None
                for tc in result_obj.reduced_coverage_tests:
                    assert tc in result_obj.coverage_tests
                    if total_tc_from_reduced is None:
                        total_tc_from_reduced = tc
                    else:
                        total_tc_from_reduced = total_tc_from_reduced + tc
                assert total_tc_from_reduced.hits_percent == 100
            if strategy == rs.BYORDER_REDUCTION:
                assert len(result_obj.reduced_coverage_tests) == len(
                    result_obj.coverage_tests
                ), f"Inconsistent sequences: {result_obj.reduced_coverage_tests} and {result_obj.coverage_tests}"
                # Both test vectors included because the naive approach works sequentially when looking
                # at the test coverages.
                # This means that the "worse" test coverage with smaller line coverage is added because it comes first
                # in the sequence. Then the "better" test coverage is also added since it increases the line coverage.
                assert len(result_obj.reduced_coverage_tests) == 2
                total_tc_from_reduced = None
                for tc in result_obj.reduced_coverage_tests:
                    assert tc in result_obj.coverage_tests
                    if total_tc_from_reduced is None:
                        total_tc_from_reduced = tc
                    else:
                        total_tc_from_reduced = total_tc_from_reduced + tc
                assert total_tc_from_reduced.hits_percent == 100
        if goal in [eu.COVER_BRANCHES, eu.COVER_CONDITIONS]:
            # In naive and furthest diff strategy tests with x = 2 and x := -2 are included
            # because each test will give 50% branch coverage and 50% condition coverage
            # and merging this together a branch/condition coverage of 100% is obtained.
            assert len(result_obj.reduced_coverage_tests) == len(
                result_obj.coverage_tests
            ), f"Inconsistent sequences: {result_obj.reduced_coverage_tests} and {result_obj.coverage_tests}"
            assert len(result_obj.reduced_coverage_tests) == 2
            total_tc_from_reduced = None
            for tc in result_obj.reduced_coverage_tests:
                assert tc in result_obj.coverage_tests
                if total_tc_from_reduced is None:
                    total_tc_from_reduced = tc
                else:
                    total_tc_from_reduced = total_tc_from_reduced + tc
            if goal is eu.COVER_BRANCHES:
                assert total_tc_from_reduced.hits_percent == 100
            if goal is eu.COVER_CONDITIONS:
                assert total_tc_from_reduced.hits_percent == 100

    def test_branch_coverage_instrumented_programs(self, tmp_path):
        for machine_model in MACHINE_MODELS:
            runner = self.get_runner(eu.COVER_BRANCHES)
            for program in (
                os.path.join(TEST_DIRECTORY, t)
                for t in (
                    "test_false_ReachError.c",
                    "test_false_ReachErrorMultiline.c",
                )
            ):
                with WorkIn(tmp_path):
                    self.check_coverage_instrumented_program(
                        runner, machine_model, program
                    )

    @staticmethod
    def check_coverage_instrumented_program(runner, machine_model, program):
        result_obj: eu.SuiteExecutionResult = runner.run(
            TEST_FILE_SIMPLE_IF, SUITE_SIMPLE_IF, machine_model
        )
        coverage: cov.TestCoverage = result_obj.coverage_total
        assert coverage.hits_percent == 100
        assert coverage.count_total == 2
        assert coverage.hits == 2

        result_obj: eu.SuiteExecutionResult = runner.run(
            program, SUITE_VALID_ZIP, machine_model
        )
        coverage = result_obj.coverage_total
        assert coverage.hits_percent == 100
        assert coverage.count_total == 3
        assert coverage.hits == 3


def _get_cov(coverage):
    return cov.TestCoverage(DUMMY_FILE, DUMMY_TEST_VECTOR_RESULT, coverage)


# pylint: disable=protected-access
class TestCoverageChecker:

    bad_test_coverages = {
        eu.COVER_LINES: _get_cov(
            cov._LinesCoverage(
                {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}
            )
        ),
        eu.COVER_BRANCHES: _get_cov(cov._BranchesCoverage({4: 0, 5: 0, 8: 0, 9: 0})),
        eu.COVER_CONDITIONS: _get_cov(
            cov._ConditionsCoverage(
                [
                    cov.ConditionsEntry(4, {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}),
                    cov.ConditionsEntry(8, {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}),
                ]
            )
        ),
    }

    perfect_test_coverages = {
        eu.COVER_LINES: _get_cov(
            cov._LinesCoverage(
                {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1}
            )
        ),
        eu.COVER_BRANCHES: _get_cov(cov._BranchesCoverage({4: 1, 5: 1, 8: 1, 9: 1})),
        eu.COVER_CONDITIONS: _get_cov(
            cov._ConditionsCoverage(
                [
                    cov.ConditionsEntry(4, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}),
                    cov.ConditionsEntry(8, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}),
                ]
            )
        ),
    }

    half_perfect_test_coverages = {
        eu.COVER_LINES: _get_cov(
            cov._LinesCoverage(
                {1: 0, 2: 1, 3: 0, 4: 1, 5: 0, 6: 1, 7: 0, 8: 1, 9: 0, 10: 1}
            )
        ),
        eu.COVER_BRANCHES: _get_cov(cov._BranchesCoverage({4: 1, 5: 0, 8: 1, 9: 0})),
        eu.COVER_CONDITIONS: _get_cov(
            cov._ConditionsCoverage(
                [
                    cov.ConditionsEntry(4, {0: 1, 1: 1, 2: 1, 3: 0, 4: 0, 5: 0}),
                    cov.ConditionsEntry(8, {0: 1, 1: 1, 2: 1, 3: 0, 4: 0, 5: 0}),
                ]
            )
        ),
    }

    half_perfect_test_coverages_complementary = {
        eu.COVER_LINES: _get_cov(
            cov._LinesCoverage(
                {1: 1, 2: 0, 3: 1, 4: 0, 5: 1, 6: 0, 7: 1, 8: 0, 9: 1, 10: 0}
            )
        ),
        eu.COVER_BRANCHES: _get_cov(cov._BranchesCoverage({4: 0, 5: 1, 8: 0, 9: 1})),
        eu.COVER_CONDITIONS: _get_cov(
            cov._ConditionsCoverage(
                [
                    cov.ConditionsEntry(4, {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}),
                    cov.ConditionsEntry(8, {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}),
                ]
            )
        ),
    }

    test_coverage_group_one = [
        bad_test_coverages,
        perfect_test_coverages,
        half_perfect_test_coverages,
        half_perfect_test_coverages_complementary,
    ]
    test_coverage_group_two = [
        bad_test_coverages,
        half_perfect_test_coverages,
        half_perfect_test_coverages_complementary,
    ]

    def test_basic_test_coverage_computations(self):
        for goal in eu.COVERAGE_GOALS.values():
            if isinstance(goal, eu.CoverFunc):
                continue
            self._check_basic_test_coverage_computations(goal)

    def _check_basic_test_coverage_computations(self, goal):
        first_extends_second, second_extends_first = self.perfect_test_coverages[
            goal
        ].coverage.compute_coverage_relation(self.bad_test_coverages[goal].coverage)
        assert first_extends_second == 1.0
        assert second_extends_first == 0.0

        total_test_coverage = (
            self.bad_test_coverages[goal] + self.perfect_test_coverages[goal]
        )
        (
            first_extends_second,
            second_extends_first,
        ) = total_test_coverage.coverage.compute_coverage_relation(
            self.perfect_test_coverages[goal].coverage
        )
        assert first_extends_second == 0.0
        assert second_extends_first == 0.0

        first_extends_second, second_extends_first = self.half_perfect_test_coverages[
            goal
        ].coverage.compute_coverage_relation(
            self.half_perfect_test_coverages_complementary[goal].coverage
        )
        assert first_extends_second == 0.5
        assert second_extends_first == 0.5

    def test_basic_coverage_computations_lines(self):
        for test_coverages in self.test_coverage_group_one:
            goal = eu.COVER_LINES
            assert test_coverages[goal].count_total == 10
            assert len(test_coverages[goal].coverage.relevant_program_lines) == 10

        assert self.half_perfect_test_coverages[goal].hits == 5
        assert not self.half_perfect_test_coverages[
            goal
        ].coverage.is_program_line_covered(1)
        assert self.half_perfect_test_coverages[goal].coverage.is_program_line_covered(
            2
        )

    def test_basic_coverage_computations_branches(self):
        for test_coverages in self.test_coverage_group_one:
            goal = eu.COVER_BRANCHES
            assert test_coverages[goal].count_total == 4
            assert len(test_coverages[goal].coverage.relevant_program_lines) == 4

        assert self.half_perfect_test_coverages[goal].hits == 2
        assert not self.half_perfect_test_coverages[
            goal
        ].coverage.is_program_line_covered(5)
        assert not self.half_perfect_test_coverages[
            goal
        ].coverage.is_program_line_covered(9)

    def test_basic_coverage_computations_conditions(self):
        for test_coverages in self.test_coverage_group_one:
            goal = eu.COVER_CONDITIONS
            assert test_coverages[goal].count_total == 12
            assert len(test_coverages[goal].coverage.relevant_program_lines) == 2

        assert self.half_perfect_test_coverages[goal].hits == 6
        assert not self.half_perfect_test_coverages[
            goal
        ].coverage.is_program_line_covered(4)
        assert not self.half_perfect_test_coverages[
            goal
        ].coverage.is_program_line_covered(8)

    def test_coverage_stragey(self):
        for goal in eu.COVERAGE_GOALS.values():
            if isinstance(goal, eu.CoverFunc):
                continue
            covs1 = [cov[goal] for cov in self.test_coverage_group_one]
            reduced_tests = rs.execute(rs.FURTHEST_DIFF_REDUCTION, covs1)
            assert self.perfect_test_coverages[goal] in reduced_tests
            assert self.half_perfect_test_coverages[goal] not in reduced_tests
            assert (
                self.half_perfect_test_coverages_complementary[goal]
                not in reduced_tests
            )
            assert self.bad_test_coverages[goal] not in reduced_tests

            covs2 = [cov[goal] for cov in self.test_coverage_group_two]
            reduced_tests = rs.execute(rs.FURTHEST_DIFF_REDUCTION, covs2)
            assert self.half_perfect_test_coverages[goal] in reduced_tests
            assert self.half_perfect_test_coverages_complementary[goal] in reduced_tests
            assert self.bad_test_coverages[goal] not in reduced_tests

            # for naive reduction the test coverage positions in the list is crucial
            reduced_tests = rs.execute(rs.BYORDER_REDUCTION, covs1)
            assert (
                self.bad_test_coverages[goal] not in reduced_tests
            ), r"Test coverage with 0% coverage in reduced test suite"
            assert (
                self.perfect_test_coverages[goal] in reduced_tests
            ), r"Test coverage with 100% coverage not in reduced test suite"
            assert (
                self.half_perfect_test_coverages[goal] not in reduced_tests
            ), r"Test coverage not increasing total coverage in reduced test suite"
            assert (
                self.half_perfect_test_coverages_complementary[goal]
                not in reduced_tests
            )

            reduced_tests = rs.execute(rs.NO_REDUCTION, self.test_coverage_group_one)
            assert not reduced_tests


def _get_harness_file_target():
    return "harness.c"


def _get_compile_target():
    return "compiled"
