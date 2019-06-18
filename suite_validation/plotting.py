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
"""Module for plotting coverage statistics"""

import os
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from suite_validation import execution_utils as eu


def _prepare_axis_for_plot(coverage_goal: str):
    if coverage_goal in [eu.COVER_BRANCHES, eu.COVER_ERRORS]:
        ylabel = "Branch Coverage (%)"
    elif coverage_goal == eu.COVER_CONDITIONS:
        ylabel = "Condition Coverage (%)"
    elif coverage_goal == eu.COVER_LINES:
        ylabel = "Line Coverage (%)"

    ax = plt.figure().gca()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0, top=100)
    ax.set_ylabel(ylabel)
    return ax


def _write_individual_coverages_plot(exec_results, coverage_goal, output_file):
    coverages = exec_results.coverage_tests
    if coverage_goal in [eu.COVER_BRANCHES, eu.COVER_ERRORS]:
        select_cov = lambda cov: cov.compute_branch_coverage()
        total_coverage = float(exec_results.branches_taken[:-1])
    elif coverage_goal == eu.COVER_CONDITIONS:
        select_cov = lambda cov: cov.compute_branch_conditions_executed()
        total_coverage = float(exec_results.branches_executed[:-1])
    elif coverage_goal == eu.COVER_LINES:
        select_cov = lambda cov: cov.compute_line_coverage()
        total_coverage = float(exec_results.lines_executed[:-1])

    ax = _prepare_axis_for_plot(coverage_goal)

    def autolabel(rects):
        """
        Attach a text label above each bar displaying its height
        """
        for rect in rects:
            height = rect.get_height()
            ax.text(
                rect.get_x() + rect.get_width() / 2.0,
                height + 0.1,
                "%.2f" % float(height),
                ha="center",
                va="bottom",
            )

    # ax.set_xticks(range(len(coverages)), [c.filename for c in coverages])
    test_names = [os.path.basename(c.test_vector.origin) for c in coverages]
    coverages_selected = [select_cov(c) * 100 for c in coverages]
    bars = ax.bar(test_names, coverages_selected, color="blue", alpha=0.7)
    autolabel(bars)

    ax.tick_params(axis="x", labelrotation="auto")
    ax.axhline(total_coverage, dashes=(1, 1), alpha=0.7)
    ax.text(
        0,
        total_coverage + 2,
        "Accumulated coverage of all tests: {}%".format(total_coverage),
    )
    plt.savefig(output_file)
    plt.clf()


def _write_coverage_sequence_plot(exec_results, coverage_goal, output_file):
    ax = _prepare_axis_for_plot(coverage_goal)
    ax.set_xlabel("First n Tests executed")
    ax.step(
        range(0, 1 + len(exec_results.coverage_sequence)),
        [0] + exec_results.coverage_sequence,
        where="post",
    )
    ax.plot(
        range(1, 1 + len(exec_results.coverage_sequence)),
        exec_results.coverage_sequence,
        "C0o",
        alpha=0.7,
    )

    # Don't show a coverage marker if the coverage didn't increase,
    # and fit at most 10 markers on the plot.
    last_cov = 0
    steps = int(len(exec_results.coverage_sequence) / 10)
    last_idx = -steps - 1
    for idx, cov in enumerate(exec_results.coverage_sequence, 1):
        if last_idx + steps <= idx and cov > last_cov:
            ax.text(idx, cov + 0.5, "%.2f" % float(cov), ha="center", va="bottom")
            last_idx = idx
        last_cov = cov

    total_coverage = exec_results.coverage_sequence[-1]
    ax.axhline(total_coverage, dashes=(1, 1))
    ax.text(
        0,
        total_coverage + 2,
        "Accumulated coverage of all tests: {}%".format(total_coverage),
    )
    plt.savefig(output_file)
    plt.clf()


def create_plots(exec_results, coverage_goal: str, output_dir: str, overwrite: bool):
    if exec_results.coverage_tests:
        individual_cov_file = os.path.join(output_dir, "individual-test-coverages.svg")
        if overwrite or not os.path.exists(individual_cov_file):
            _write_individual_coverages_plot(
                exec_results, coverage_goal, individual_cov_file
            )

    if exec_results.coverage_sequence:
        cov_seq_file = os.path.join(output_dir, "coverage-sequence.svg")
        if overwrite or not os.path.exists(cov_seq_file):
            _write_coverage_sequence_plot(exec_results, coverage_goal, cov_seq_file)
