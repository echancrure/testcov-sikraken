# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020 Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module for plotting coverage statistics"""

import os
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from suite_validation import execution_utils as eu


AXIS_PADDING = 0
BAR_WIDTH = 0.3


def _prepare_axis_for_plot(coverage_goal: str, total_coverage: float, test_count: int):
    if eu.uses_branch_coverage(coverage_goal):
        ylabel = "Branch Coverage (%)"
    elif eu.uses_condition_coverage(coverage_goal):
        ylabel = "Condition Coverage (%)"
    elif eu.uses_line_coverage(coverage_goal):
        ylabel = "Line Coverage (%)"

    ax = plt.figure().gca()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("# Test Executed")
    ax.set_ylim(bottom=AXIS_PADDING, top=110)
    ax.set_xlim(left=AXIS_PADDING, right=test_count)
    ax.set_yticks(
        [n for n in range(0, 100, 20) if n < total_coverage] + [total_coverage] + [100]
    )
    ax.spines["left"].set_bounds(0, total_coverage)
    ax.spines["bottom"].set_bounds(0, test_count + 0.5)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.set_ylabel(ylabel)
    return ax


def _write_coverages_plot(exec_results, coverage_goal, output_file):
    coverages = exec_results.coverage_tests
    test_count = len(exec_results.tests)
    total_coverage = exec_results.coverage_total.hits_percent

    xlim = len(exec_results.results) + 1
    ax = _prepare_axis_for_plot(coverage_goal, total_coverage, test_count)

    if coverages:
        coverages_selected = [
            c.hits_percent if c.hits_percent else 0 for c in coverages
        ]

        ax.bar(
            range(1, len(coverages_selected) + 1),
            coverages_selected,
            color="blue",
            alpha=0.7,
            width=BAR_WIDTH,
            bottom=0,
            label="Individual coverage",
        )

        ax.set_xlim(0, xlim)
        xtick_step_size = int(xlim / 10) + 1
        ax.set_xticks(range(0, xlim, xtick_step_size))

    if test_count > 1:
        if exec_results.coverage_sequence:
            assert (
                total_coverage == exec_results.coverage_sequence[-1]
            ), "Final coverage of coverage sequence not same as total coverage reported"
            assert len(exec_results.coverage_sequence) == len(
                exec_results.results
            ), f"List lengths don't match: {exec_results.coverage_sequence} vs. {exec_results.results}"

            ax.step(
                [n - BAR_WIDTH / 2.0 for n in range(1, xlim)]
                + [xlim - 1 + BAR_WIDTH / 2.0],
                exec_results.coverage_sequence + [exec_results.coverage_sequence[-1]],
                where="post",
                color="violet",
                alpha=1,
                linewidth=2,
                label="Accumulated coverage",
            )
            # ax.plot([n - BAR_WIDTH / 2.0 for n in range(1, xlim)], exec_results.coverage_sequence, "C0o", alpha=0.7)

            # Text labels at individual steps.
            # Don't show a coverage marker if the coverage didn't increase,
            # and fit at most 10 markers on the plot.
            # last_cov = 0
            # steps = int(len(exec_results.coverage_sequence) / 10)
            # last_idx = -steps - 1
            # for idx, cov in enumerate(exec_results.coverage_sequence, 1):
            #    if (
            #        last_idx + steps <= idx
            #        and exec_results.coverage_sequence[-1] > cov > last_cov
            #        # and (not coverages_selected or cov != coverages_selected[idx-1])
            #    ):
            #        ax.text(idx, cov + 1.5, "%.2f" % float(cov), ha="center", va="bottom")
            #        last_idx = idx
            #    last_cov = cov

            ax.legend()
        else:
            ax.axhline(total_coverage, dashes=(1, 1), alpha=0.7)
            ax.text(
                1,
                total_coverage + 2,
                "Accumulated coverage",
                ha="left",
                va="bottom",
                bbox=dict(facecolor="white", edgecolor=None, linewidth=0, alpha=0),
                fontsize=10,
            )

    plt.tight_layout()
    plt.savefig(output_file)
    plt.clf()


def create_plots(exec_results, coverage_goal: str, output_dir: str):
    cov_file = os.path.join(output_dir, "coverage.svg")
    _write_coverages_plot(exec_results, coverage_goal, cov_file)
