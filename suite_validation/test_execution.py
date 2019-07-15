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
"""Tests for execution module."""

import os
import shutil
import subprocess
import tempfile
import itertools
from nose.tools import timed
from nose.tools import raises
from nose.tools import eq_
import suite_validation.execution as ex
import suite_validation.execution_utils as eu
import suite_validation

MODULE_DIRECTORY = os.path.join(
    os.path.dirname(suite_validation.__file__), os.path.pardir
)
TEST_DIRECTORY = os.path.join(MODULE_DIRECTORY, "test")
TEST_FILE_WITHOUT_ERR = os.path.join(TEST_DIRECTORY, "test.c")
TEST_FILE_WITH_ERR = os.path.join(TEST_DIRECTORY, "test_false.c")
TEST_FILE_WITH_NO_TERMINATION = os.path.join(TEST_DIRECTORY, "test_no-termination.c")
TEST_FILE_WITH_STRINGS = os.path.join(TEST_DIRECTORY, "test_string.c")
TEST_FILE_COVERAGE = os.path.join(TEST_DIRECTORY, "test_coverages.c")

TEST_HARNESS = os.path.join(TEST_DIRECTORY, "test_harness.c")

SUITE_DIR = os.path.join(TEST_DIRECTORY, "suites")
SUITE_VALID_ZIP = os.path.join(SUITE_DIR, "suite-valid.zip")
SUITE_VALID_NESTED_ZIP = os.path.join(SUITE_DIR, "suite-valid-nested.zip")
SUITE_VALID_STRINGS = os.path.join(SUITE_DIR, "suite-string.zip")
SUITE_INVALID_ZIP = os.path.join(SUITE_DIR, "suite-metadata-missing.zip")
SUITE_COVERAGE = os.path.join(SUITE_DIR, "suite-coverages.zip")

MACHINE_MODELS = (eu.MACHINE_MODEL_32, eu.MACHINE_MODEL_64)


class TempDirExecutor:
    def __init__(self):
        self.temp_dir = None
        self._old_dir = "."

    def setup(self):
        self.temp_dir = _get_test_directory()
        self._old_dir = os.path.abspath(".")
        os.chdir(self.temp_dir)

    def teardown(self):
        os.chdir(self._old_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestHarness(TempDirExecutor):
    """Tests for harness creation with ex.HarnessCreator."""

    def test_harness_without_test_vector_compilable(self):
        self._check_compilable()

    def test_harness_with_test_vector_compilable(self):
        vectors = list()

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
            yield self._check_compilable, tv

    @staticmethod
    def _check_compilable(test_vector=None):
        compile_cmd = ["gcc", "-x", "c", "-include", TEST_FILE_WITHOUT_ERR, "-"]

        harness = ex.HarnessCreator().convert(TEST_FILE_WITHOUT_ERR, test_vector)

        compile_exec = subprocess.Popen(compile_cmd, stdin=subprocess.PIPE)
        compile_exec.communicate(harness.encode())
        returncode = compile_exec.poll()

        eq_(returncode, 0, "Compilation failed: %s" % compile_cmd)


class TestExecutionRunner(TempDirExecutor):
    """Tests for ex.ExecutionRunner."""

    @staticmethod
    def get_runner(machine_model, timelimit):
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.ExecutionRunner(
            machine_model, timelimit, harness_file, compile_output_file
        )

    def test_harness_creation(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_harness_creation, machine_model

    def _check_harness_creation(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)

        try:
            output_file = runner.get_executable_harness(TEST_FILE_WITHOUT_ERR)
        except ex.ExecutionError as e:
            assert False, "Harness creation failed: %s" % e

        assert os.path.exists(output_file), "Harness %s not found" % output_file

    def test_harness_compile(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_harness_creation, machine_model

    def _check_harness_compile(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        try:
            out_file = runner.compile(TEST_FILE_WITHOUT_ERR, TEST_HARNESS, out_file)

        except ex.ExecutionError as e:
            assert False, "Compilation failed: %s" % e
        assert os.path.exists(out_file)

    def test_invalid_harness_compile_throws_error(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_invalid_harness_compile_throws_error, machine_model

    @raises(ex.ExecutionError)
    def _check_invalid_harness_compile_throws_error(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        runner.compile(TEST_FILE_WITHOUT_ERR, "foobar-harness.c", out_file)

    def test_invalid_program_compile_throws_error(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_invalid_harness_compile_throws_error, machine_model

    @raises(ex.ExecutionError)
    def _check_invalid_program_compile_throws_error(self, machine_model):
        runner = self.get_runner(machine_model, timelimit=None)
        _, out_file = tempfile.mkstemp()

        runner.compile("foobar-program.c", TEST_HARNESS, out_file)

    def test_execution_run_result_unknown(self):
        simple_vector = eu.TestVector("dummy", "dummy.xml")
        simple_vector.add("1")

        for machine_model in MACHINE_MODELS:
            for timelimit in (None, 5, 10, 99999):
                yield self._check_test_execution_runs, machine_model, timelimit, TEST_FILE_WITHOUT_ERR, simple_vector, eu.TestResult.UNKNOWN

    def _check_test_execution_runs(
        self, machine_model, timelimit, test_file, test_vector, expected
    ):
        if timelimit:
            timed(timelimit * 1.2)

        runner = self.get_runner(machine_model, timelimit)

        run_result = runner.run(test_file, test_vector)

        eq_(run_result, expected)

    def test_execution_run_result_known(self):
        covering_vector = eu.TestVector("covers_test", "covers_test.c")
        covering_vector.add("'a'")
        covering_vector.add("5")
        covering_vector.add("0x10")

        missing_vector = eu.TestVector("misses_test", "misses_test.c")
        missing_vector.add("'z'")
        missing_vector.add("5")
        missing_vector.add("0x0f")

        for machine_model in MACHINE_MODELS:
            for timelimit in (None, 5, 10):
                yield self._check_test_execution_runs, machine_model, timelimit, TEST_FILE_WITH_ERR, covering_vector, eu.TestResult.COVERS

        for machine_model in MACHINE_MODELS:
            for timelimit in (None, 5, 10):
                yield self._check_test_execution_runs, machine_model, timelimit, TEST_FILE_WITH_ERR, missing_vector, eu.TestResult.UNKNOWN

    def test_execution_run_non_terminating_with_timelimit(self):
        empty_vector = eu.TestVector("dummy", "dummy.xml")
        timelimit = 3

        for machine_model in MACHINE_MODELS:
            yield self._check_test_execution_runs, machine_model, timelimit, TEST_FILE_WITH_NO_TERMINATION, empty_vector, eu.TestResult.ABORTED


class TestCoverageMeasuringExecutionRunner(TestExecutionRunner):
    """Tests for ex.CoverageMeasuringExecutionRunner."""

    @staticmethod
    def get_runner(machine_model, timelimit):
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.CoverageMeasuringExecutionRunner(
            machine_model, timelimit, harness_file, compile_output_file
        )

    def test_get_coverage_single_execution(self):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        for machine_model in MACHINE_MODELS:
            yield self._check_coverage_multiple_executions, machine_model, [
                vector_going_one_way
            ]

    def test_get_coverage_multiple_executions(self):
        vector_going_one_way = eu.TestVector("vector1", "vector1.xml")
        vector_going_one_way.add("5")

        vector_going_other_way = eu.TestVector("vector2", "vector2.xml")
        vector_going_other_way.add("-5")

        for machine_model in MACHINE_MODELS:
            yield self._check_coverage_multiple_executions, machine_model, [
                vector_going_one_way,
                vector_going_other_way,
            ]

    def _check_coverage_multiple_executions(self, machine_model, vectors):
        runner = self.get_runner(machine_model, None)
        test_file = TEST_FILE_WITHOUT_ERR

        old_line_cov, old_branch_cov = 0, 0
        for tv in vectors:
            runner.run(test_file, tv)
            tracefile_folder = ex.SuiteExecutor.create_tracefile_folder()
            target_tracefile = ex.SuiteExecutor.get_tracefile_path(tracefile_folder)
            coverage = runner.get_coverage(test_file, target_tracefile)

            assert coverage.line_coverage > 0, "Line coverage at 0"
            assert coverage.branch_coverage > 0, "Branch coverage at 0"
            assert (
                coverage.line_coverage > old_line_cov
            ), "Line coverage didn't increase"
            assert (
                coverage.branch_coverage > old_branch_cov
            ), "Branch coverage didn't increase"

            old_line_cov = coverage.line_coverage
            old_branch_cov = coverage.branch_coverage


class TestSuiteExecutor(TempDirExecutor):
    """Tests for ex.SuiteExecutor."""

    def __init__(self):
        super().__init__()
        self.program_file = TEST_FILE_WITH_ERR

    @staticmethod
    def get_runner(
        goal=eu.COVER_BRANCHES,
        timelimit=None,
        compute_sequence=True,
        compute_individuals=True,
    ):
        harness_file = _get_harness_file_target()
        compile_output_file = _get_compile_target()
        return ex.SuiteExecutor(
            goal,
            timelimit,
            harness_file,
            compile_output_file,
            compute_sequence=compute_sequence,
            isolate_tests=False,
            compute_individuals=compute_individuals,
        )

    def test_run_suite_valid(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_run_suite_valid, machine_model, SUITE_VALID_ZIP

    def test_run_nested_suite_valid(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_run_suite_valid, machine_model, SUITE_VALID_NESTED_ZIP

    def _check_run_suite_valid(self, machine_model, suite_location):
        runner = self.get_runner()

        result_obj = runner.run(self.program_file, suite_location, machine_model)
        results = result_obj.results
        lines = result_obj.coverage_total.line_coverage
        conds_ex = result_obj.coverage_total.condition_coverage
        branches = result_obj.coverage_total.branch_coverage

        eq_(len(results), 2, "Not both tests executed")
        assert (
            results.count(eu.TestResult.COVERS) == 1
            and results.count(eu.TestResult.UNKNOWN) == 1
        ), (
            "Expected exactly one result to be %s and one to be %s: %s"
            % (eu.TestResult.COVERS, eu.TestResult.UNKNOWN, results)
        )
        assert (
            lines and conds_ex and branches
        ), "Coverage information invalid: %s, %s, %s" % (lines, conds_ex, branches)

    @staticmethod
    def _check_file_exists(filename):
        assert os.path.exists(filename), "File doesn't exist: %s" % filename

    def test_run_suite_without_metadata_throws_error(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_run_suite_without_metadata_throws_error, machine_model, SUITE_INVALID_ZIP

    @raises(ex.ExecutionError)
    def _check_run_suite_without_metadata_throws_error(
        self, machine_model, suite_location
    ):
        runner = self.get_runner()

        runner.run(self.program_file, suite_location, machine_model)

    def test_run_suite_with_non_terminating_program(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_run_suite_with_non_terminating_program, machine_model, SUITE_VALID_ZIP

    def _check_run_suite_with_non_terminating_program(
        self, machine_model, suite_location
    ):
        runner = self.get_runner(timelimit=2)

        result_obj = runner.run(
            TEST_FILE_WITH_NO_TERMINATION, suite_location, machine_model
        )
        results = result_obj.results

        assert len(results) == 2 and all(
            r == eu.TestResult.ABORTED for r in results
        ), "Expected two results '%s': %s" % (eu.TestResult.ABORTED, results)

    def test_run_suite_with_string_inputs(self):
        for machine_model in MACHINE_MODELS:
            yield self._check_run_suite_with_string_inputs, machine_model, SUITE_VALID_STRINGS

    def _check_run_suite_with_string_inputs(self, machine_model, suite_location):
        runner = self.get_runner(timelimit=2)

        result_obj = runner.run(TEST_FILE_WITH_STRINGS, suite_location, machine_model)
        results = result_obj.results

        assert (
            len(results) == 2
            and any(r == eu.TestResult.COVERS for r in results)
            and any(r == eu.TestResult.UNKNOWN for r in results)
        ), (
            "Expected results '%s' and '%s', but got: %s"
            % (eu.TestResult.COVERS, eu.TestResult.UNKNOWN, results)
        )

    def test_compute_individuals_produces_same_coverage(self):
        for machine_model in MACHINE_MODELS:
            for goal in eu.COVERAGE_GOALS.values():
                runners = [
                    self.get_runner(goal),
                    self.get_runner(goal, compute_individuals=False),
                    self.get_runner(goal, compute_sequence=False),
                    self.get_runner(
                        goal, compute_sequence=False, compute_individuals=False
                    ),
                ]
                runners_tuples = itertools.combinations(runners, 2)

                for runner1, runner2 in runners_tuples:
                    yield self._check_coverage_results_equal, runner1, runner2, SUITE_VALID_ZIP, machine_model

    @staticmethod
    def _get_config_str(runner):
        # pylint: disable=protected-access
        return "SuiteExecutor[ComputeInd={},ComputeSeq={}]".format(
            runner._compute_individual_test_coverages, runner._compute_sequence
        )

    def _check_coverage_results_equal(
        self, runner1, runner2, suite_location, machine_model
    ):
        result_obj = runner1.run(self.program_file, suite_location, machine_model)
        lines1, conditions1, branches1 = (
            result_obj.coverage_total.line_coverage,
            result_obj.coverage_total.condition_coverage,
            result_obj.coverage_total.branch_coverage,
        )

        result_obj = runner2.run(self.program_file, suite_location, machine_model)
        lines2, conditions2, branches2 = (
            result_obj.coverage_total.line_coverage,
            result_obj.coverage_total.condition_coverage,
            result_obj.coverage_total.branch_coverage,
        )

        config1 = self._get_config_str(runner1)
        config2 = self._get_config_str(runner2)
        err_msg = "Unequal for {} and {}".format(config1, config2)

        eq_(lines1, lines2, err_msg + ": {} vs {}".format(lines1, lines2))
        eq_(
            conditions1,
            conditions2,
            err_msg + ": {} vs {}".format(conditions1, conditions2),
        )
        eq_(branches1, branches2, err_msg + ": {} vs {}".format(branches1, branches2))

    def test_coverages_correct(self):
        for machine_model in MACHINE_MODELS:
            for goal in eu.COVERAGE_GOALS.values():
                runner = self.get_runner(goal)
                yield self._check_coverage_results_correct, runner, machine_model

    @staticmethod
    def _check_coverage_results_correct(runner, machine_model):
        result_obj = runner.run(TEST_FILE_COVERAGE, SUITE_COVERAGE, machine_model)
        cov = result_obj.coverage_total

        eq_(cov.line_coverage, 68.75)
        eq_(cov.branch_coverage, 50)
        eq_(cov.condition_coverage, 33.33)
        eq_(cov.lines_total, 16)
        eq_(cov.branches_total, 8)
        eq_(cov.conditions_total, 12)


def _get_test_directory():
    return tempfile.mkdtemp(prefix="tf_test_exec")


def _get_harness_file_target():
    return "foobar-harness.c"


def _get_compile_target():
    return "compiled"
