# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module for coverage of individual tests"""

from functools import reduce
import os
import shutil

from typing import Dict, Tuple, List, Optional, Sequence
from abc import ABCMeta, abstractmethod

import numpy as np
from suite_validation import execution_utils as eu
from suite_validation import _logger as logging


MODULE_DIRECTORY = os.path.join(os.path.dirname(__file__), os.path.pardir)
LLVM_GCOV_BINARY = os.path.join(MODULE_DIRECTORY, "bin/llvm-gcov")
TRACE_FILE_CONDITION_NOT_VISITED = "-"

_FILEPATH = "SF:"
_LINE_HIT_COUNTER = "DA"
_END_OF_RECORD = "end_of_record"
_BRANCH_LINE_CONDITION_HIT_COUNTER = "BRDA:"


class _CoverageComparable:
    """
    A class that implements CoverageComparable must be able to compute the coverage relation between an object of the
    class and another object of the same class. The computation of a coverage relation must return two values: The first
    value represents the ratio of the measured unit (for instance line coverage) that the class object covers but that
    is not covered by the other object. The second value represents the ratio of the measured unit that the other object
    covers but is not covered by the class object.
    Moreover, an instance of a class that implements CoverageComparable must be mergable with another instance of the
    same class.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def compute_coverage_relation(
        self, other: "_CoverageComparable"
    ) -> Tuple[float, float]:
        """
        Computes the coverage relation to another instance that implements CoverageComparable.
        The returned tuple contains two values in interval [0,1].
        :param other:
        :return: Tuple(covered_only_by_self, covered_only_by_other)
        """
        raise NotImplementedError

    @abstractmethod
    def is_coverage_for_program_line_extended(
        self, other: "_CoverageComparable", pl
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_program_line_covered(self, pl) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def relevant_program_lines(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def hits(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def count_total(self) -> int:
        raise NotImplementedError

    @property
    def hits_percent(self) -> float:
        if self.count_total == 0:
            return 100
        return round(self.hits / self.count_total * 100, 2)

    @abstractmethod
    def merge(self, cov: "_CoverageComparable") -> "_CoverageComparable":
        raise NotImplementedError

    def covers(self, other: "_CoverageComparable") -> bool:
        only_covered_by_self, only_covered_by_other = self.compute_coverage_relation(
            other
        )
        return only_covered_by_other <= 0 < only_covered_by_self

    def is_covered(self, other: "_CoverageComparable") -> bool:
        only_covered_by_self, only_covered_by_other = self.compute_coverage_relation(
            other
        )
        return only_covered_by_self <= 0 < only_covered_by_other

    def is_coverage_extended(self, other: "_CoverageComparable") -> bool:
        _, only_covered_by_other = self.compute_coverage_relation(other)
        return only_covered_by_other > 0

    def __eq__(self, other):
        try:
            cov = float(other)
            return self.hits_percent == cov
        except TypeError:
            return False

    def __lt__(self, other):
        try:
            cov = float(other)
            return self.hits_percent < cov
        except TypeError:
            return False

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return self > other or self == other


class ConditionsEntry:
    """
    An instance of ConditionsEntry has a dictionary with indices as keys to address the conditions and counter numbers
    as corresponding values which say how often the conditions have been hit. Moreover, an instance has a program line
    to relate to the program where the conditions appear. Note that ConditionsEntry does not implement
    CoverageComparable.
    An instance of ConditionsEntry is fully covered when each indices has a corresponding counter value that is greater
    than zero.
    """

    def __init__(self, program_line: int, conditions_hit_counter: Dict[int, int]):
        self.program_line = program_line
        self.conditions_hit_counter = conditions_hit_counter

    @property
    def conditions_total(self) -> int:
        return len(self.conditions_hit_counter)

    @property
    def conditions_hit(self) -> int:
        return len([v for v in self.conditions_hit_counter.values() if v > 0])

    @property
    def conditions_indices(self):
        return self.conditions_hit_counter.keys()

    @property
    def is_program_line_covered(self) -> bool:
        return all(c > 0 for c in self.conditions_hit_counter.values())

    @property
    def relevant_program_lines(self):
        return [self.program_line]

    @staticmethod
    def merge(
        entry1: "ConditionsEntry", entry2: "ConditionsEntry"
    ) -> "ConditionsEntry":
        assert entry1.program_line == entry2.program_line
        summarized_conditions_hit_counter = {}
        for condition_index in entry1.conditions_hit_counter:
            summarized_conditions_hit_counter[condition_index] = (
                entry1.conditions_hit_counter[condition_index]
                + entry2.conditions_hit_counter[condition_index]
            )
        return ConditionsEntry(entry1.program_line, summarized_conditions_hit_counter)

    def same_program_line(self, other: "ConditionsEntry") -> bool:
        return self.program_line == other.program_line

    def set_condition_to_hit_counter(self, index: int, number_of_condition_taken: int):
        self.conditions_hit_counter[index] = number_of_condition_taken

    def compute_coverage_relation(self, other: "ConditionsEntry") -> Tuple[int, int]:
        assert self.program_line == other.program_line
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        for key in self.conditions_indices:
            if (
                self.conditions_hit_counter[key]
                <= 0
                < other.conditions_hit_counter[key]
            ):
                conditions_only_covered_by_other += 1
            if (
                other.conditions_hit_counter[key]
                <= 0
                < self.conditions_hit_counter[key]
            ):
                conditions_only_covered_by_self += 1
        return conditions_only_covered_by_self, conditions_only_covered_by_other

    def is_coverage_for_program_line_extended(self, other: "ConditionsEntry"):
        return any(
            hit_counter <= 0 < other.conditions_hit_counter[pl]
            for pl, hit_counter in self.conditions_hit_counter.items()
        )

    def __eq__(self, other):
        if not isinstance(other, ConditionsEntry):
            return False
        return (
            self.conditions_hit == other.conditions_hit
            and self.same_program_line(other)
            and self.conditions_hit_counter == other.conditions_hit_counter
        )

    def __repr__(self):
        condition_repr = "\n".join(
            f"\tCondition {cond}: {hits}"
            for cond, hits in self.conditions_hit_counter.items()
        )
        return f"Line {self.program_line}:\n{condition_repr}"

    def __str__(self):
        return self.__repr__()


class _ConditionsCoverage(_CoverageComparable):
    """
    Contains a list of ConditionsEntry to represent all ConditionEntries that appear in the program.
    Each ConditionsEntry is assigned to a certain program line. A conditions coverage satisfies full coverage
    when each ConditionsEntry satisfies full coverage.
    """

    def __init__(self, conditions_entries: List[ConditionsEntry]):
        self.conditions_entries = conditions_entries

    @property
    def hits(self) -> int:
        return sum(e.conditions_hit for e in self.conditions_entries)

    @property
    def count_total(self) -> int:
        number_of_conditions_found = 0
        for condition_entry in self.conditions_entries:
            number_of_conditions_found += condition_entry.conditions_total
        return number_of_conditions_found

    @property
    def relevant_program_lines(self):
        return [entry.program_line for entry in self.conditions_entries]

    def merge(self, cov: "_ConditionsCoverage") -> "_ConditionsCoverage":
        merged = [
            ConditionsEntry.merge(e1, e2)
            for e1 in self.conditions_entries
            for e2 in cov.conditions_entries
            if e1.same_program_line(e2)
        ]
        return _ConditionsCoverage(merged)

    def get_conditions_entry(self, program_line) -> Optional[ConditionsEntry]:
        return next(
            iter(
                [e for e in self.conditions_entries if e.program_line == program_line]
            ),
            None,
        )

    def compute_coverage_relation(
        self, other: "_ConditionsCoverage"
    ) -> Tuple[float, float]:
        conditions_only_covered_by_self = 0
        conditions_only_covered_by_other = 0
        entries_per_line = (
            (e1, e2)
            for e1 in self.conditions_entries
            for e2 in other.conditions_entries
            if e1.same_program_line(e2)
        )
        for conditions_self, conditions_other in entries_per_line:
            (
                current_only_self,
                current_only_other,
            ) = conditions_self.compute_coverage_relation(conditions_other)
            conditions_only_covered_by_self += current_only_self
            conditions_only_covered_by_other += current_only_other
        if self.count_total == 0:
            return 0.0, 0.0
        return (
            float(conditions_only_covered_by_self) / float(self.count_total),
            float(conditions_only_covered_by_other) / float(self.count_total),
        )

    def is_program_line_covered(self, pl) -> bool:
        if pl not in self.relevant_program_lines:
            return False
        e = self.get_conditions_entry(pl)
        if not e:
            return False
        return e.is_program_line_covered

    def is_coverage_for_program_line_extended(
        self, other: "_ConditionsCoverage", pl
    ) -> bool:
        this_entry = self.get_conditions_entry(pl)
        other_entry = other.get_conditions_entry(pl)
        if not this_entry or not other_entry:
            return False
        return this_entry.is_coverage_for_program_line_extended(other_entry)

    def __eq__(self, other):
        if super().__eq__(other):
            return True
        if not isinstance(other, _ConditionsCoverage):
            return False
        return self.conditions_entries == other.conditions_entries

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.conditions_entries}]"

    def __str__(self):
        return f"{self.hits_percent}% condition coverage"


class _LinesCoverage(_CoverageComparable):
    """
    Contains a dict with the program lines as keys and hit numbers as corresponding values. If each program line has
    a hit number greater than zero the program is fully covered regarding the line coverage.
    """

    def __init__(self, lines_hit: Dict[int, int]):
        self.hit_counter = lines_hit

    @property
    def hits(self) -> int:
        lines_taken = 0
        for program_line in self.relevant_program_lines:
            if self.hit_counter[program_line] > 0:
                lines_taken += 1
        return lines_taken

    @property
    def count_total(self) -> int:
        return len(self.relevant_program_lines)

    @property
    def relevant_program_lines(self):
        return self.hit_counter.keys()

    def merge(self, cov: "_LinesCoverage"):
        summarized_lines_coverage = {
            l: self.hit_counter[l] + cov.hit_counter[l] for l in self.hit_counter
        }
        return _LinesCoverage(summarized_lines_coverage)

    def compute_coverage_relation(self, other: "_LinesCoverage") -> Tuple[float, float]:
        lines_only_covered_by_self = 0
        lines_only_covered_by_other = 0
        for program_line in self.relevant_program_lines:
            if self.hit_counter[program_line] <= 0 < other.hit_counter[program_line]:
                lines_only_covered_by_other += 1
            if other.hit_counter[program_line] <= 0 < self.hit_counter[program_line]:
                lines_only_covered_by_self += 1
        if self.count_total == 0:
            return 0.0, 0.0
        return (
            float(lines_only_covered_by_self) / float(self.count_total),
            float(lines_only_covered_by_other) / float(self.count_total),
        )

    def is_program_line_covered(self, pl) -> bool:
        return self.hit_counter[pl] > 0

    def is_coverage_for_program_line_extended(
        self, other: "_LinesCoverage", pl
    ) -> bool:
        return not self.is_program_line_covered(pl) and other.is_program_line_covered(
            pl
        )

    def __eq__(self, other):
        if super().__eq__(other):
            return True
        if not isinstance(other, _LinesCoverage):
            return False
        return self.hit_counter == other.hit_counter

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.hit_counter}]"

    def __str__(self):
        return f"{self.hits_percent}% line coverage"


class _BranchesCoverage(_LinesCoverage):
    def __str__(self):
        return f"{self.hits_percent}% branch coverage"


class TestCoverage:
    """
    Contains the line coverage, branch coverage and conditions coverage. One of these coverage kinds can be
    extracted by using the coverage goal in the execution.
    The dictionary test_vector_results stores for each test vector the test result.
    """

    def __init__(
        self,
        file_name: str,
        test_vector_results: Dict[eu.TestVector, eu.TestResult],
        coverage: Optional[_CoverageComparable] = None,
    ):
        self.filename = file_name
        self.test_vector_results = test_vector_results
        self.coverage = coverage

    @property
    def test_vectors(self):
        return [*self.test_vector_results]

    @property
    def hits(self):
        if not self.coverage:
            return 0
        return self.coverage.hits

    @property
    def count_total(self):
        if not self.coverage:
            return 0
        return self.coverage.count_total

    @property
    def hits_percent(self):
        if not self.coverage:
            return 0
        return self.coverage.hits_percent

    def test_vectors_as_string(self):
        # Normally this method is called when the test coverage for an individual test is printed. If so this method
        # returns the origin of the only test vector.
        if not self.test_vectors:
            return ""
        out = ""
        separator = " | "
        i = 0
        while i < len(self.test_vectors) - 1:
            out += self.test_vectors[i].origin
            out += separator
        out += self.test_vectors[i].origin
        return out

    def __add__(self, other):
        if not isinstance(other, TestCoverage):
            raise ValueError()
        if not self.filename == other.filename:
            raise ValueError(
                f"Filenames between coverages do not match: {self.filename} and {other.filename}"
            )

        summarized_test_vector_results = {
            **other.test_vector_results,
            **self.test_vector_results,
        }
        covs = [c for c in (self.coverage, other.coverage) if c]
        if not covs:
            summarized_coverage = None
        elif len(covs) == 1:
            summarized_coverage = covs[0]
        else:
            summarized_coverage = reduce(lambda cov1, cov2: cov1.merge(cov2), covs)

        return TestCoverage(
            self.filename, summarized_test_vector_results, summarized_coverage
        )

    def __eq__(self, other):
        if not isinstance(other, TestCoverage):
            return False
        return (
            self.filename == other.filename
            and self.test_vector_results == other.test_vector_results
            and self.coverage == other.coverage
        )

    def __repr__(self):
        return f"""{self.__class__.__name__}[
    {self.filename},
    {self.coverage},
    {self.test_vector_results}]"""

    def __str__(self):
        results = [v.name for v in self.test_vector_results]
        return f"{results} on {self.filename}: {self.coverage}"


def remove_prefix(line, prefix):
    return line[len(prefix) :]


def _examine_line_with_condition(
    line_with_condition_info, conditions_entries: List[ConditionsEntry]
):
    chunks = line_with_condition_info.split(",")
    # chunks should be [program_line, block-number, branch-number, taken]
    assert len(chunks) == 4
    program_line = chunks[0]
    condition_index = chunks[2]
    number_of_condition_taken = chunks[3]
    if program_line.isdigit() and condition_index.isdigit():
        program_line = int(program_line)
        condition_index = int(condition_index)
    else:
        logging.error(
            "Trace file corrupted. Program line or branch number not a number"
        )
        return
    if number_of_condition_taken == TRACE_FILE_CONDITION_NOT_VISITED:
        number_of_condition_taken = 0
    else:
        number_of_condition_taken = int(number_of_condition_taken)

    _append_to_conditions_entries(
        conditions_entries, program_line, condition_index, number_of_condition_taken
    )


def _append_to_conditions_entries(
    conditions_entries: List[ConditionsEntry],
    program_line,
    condition_index,
    number_of_condition_taken,
):
    """
    Takes the condition_entry from conditions_entries by using the program_line. If no condition_entry is found
    a new condition_entry is created. The value for the key branch_index is overwritten with number_of_branch_taken.
    :param conditions_entries: the list of conditions_entries found so far in the trace file
    :param program_line: the program line for which branch_index and number_of_branch_taken is applied
    :param condition_index: a unique value to address the condition
    :param number_of_condition_taken: the number how often the condition is taken
    :return:
    """
    condition_entry = next(
        iter([e for e in conditions_entries if e.program_line == program_line]), None
    )
    if condition_entry is None:
        condition_entry = ConditionsEntry(program_line, {})
        conditions_entries.append(condition_entry)
    condition_entry.set_condition_to_hit_counter(
        condition_index, number_of_condition_taken
    )


def _get_lcov_body(lcov_lines: List[str], relevant_program_name: str):
    """Returns that suffix of the list that starts with the coverage data relevant for the given program name.
    Strips from the beginning of the given list all data irrelevant."""
    start = None
    stop = None
    for idx, line in enumerate(lcov_lines):
        if line.startswith(_FILEPATH):
            absolute_file_path = remove_prefix(line, _FILEPATH).strip()
            if os.path.basename(absolute_file_path) == relevant_program_name:
                start = idx

        elif start is not None and line.startswith(_END_OF_RECORD):
            stop = idx + 1
            break
    assert (
        start is not None
    ), f"Missing {_FILEPATH} in lcov file for {relevant_program_name}"
    assert stop is not None
    return lcov_lines[start:stop]


def _parse_for_condition_coverage(
    single_lcov_line, conditions_entries
) -> Tuple[int, int]:
    if single_lcov_line.startswith(_BRANCH_LINE_CONDITION_HIT_COUNTER):
        line_with_condition_information = remove_prefix(
            single_lcov_line, _BRANCH_LINE_CONDITION_HIT_COUNTER
        )
        _examine_line_with_condition(
            line_with_condition_information, conditions_entries
        )


def _get_condition_coverage(lcov_lines):
    conditions_entries = []

    for line in lcov_lines:
        _parse_for_condition_coverage(line, conditions_entries)
    return _ConditionsCoverage(conditions_entries)


def _get_line_hits(
    lcov_lines: Sequence[str], relevant_line_numbers: Optional[Sequence[int]]
) -> Dict[int, int]:
    lines = np.array(lcov_lines)
    table = np.char.partition(lines, ":")
    line_entries = table[table[:, 0] == _LINE_HIT_COUNTER][:, 2]
    pairs = np.char.partition(line_entries, ",")[:, [0, 2]].astype(int)
    if relevant_line_numbers is not None:
        pairs = pairs[np.isin(pairs[:, 0], relevant_line_numbers)]
    return dict(pairs)


def _get_line_coverage(
    lcov_lines: Sequence[str], relevant_line_numbers: Optional[Sequence[int]], goal
) -> Dict[int, int]:
    if eu.uses_branch_coverage(goal) and relevant_line_numbers is None:
        return None

    hits = _get_line_hits(lcov_lines, relevant_line_numbers)
    if eu.uses_line_coverage(goal):
        return _LinesCoverage(hits)
    if eu.uses_branch_coverage(goal):
        return _BranchesCoverage(hits)
    raise AssertionError(f"Unhandled goal {goal}")


def _get_coverage_from_tracefile(
    program_name,
    trace_file,
    coverage_goal,
    relevant_line_numbers=None,
) -> Optional[_CoverageComparable]:
    logging.debug("Extracting coverage from created tracefile")

    # Values can be read directly from the trace file and are only used for assertion checks
    logging.debug("Reading in file")
    with open(trace_file, encoding="UTF-8") as inp:
        lines = [l.strip() for l in inp.readlines()]
    logging.debug("Done reading in file")
    logging.debug("Handling lcov-data preamble")
    lcov_lines = _get_lcov_body(lines, program_name)
    logging.debug("Done handling lcov-data preamble")
    logging.debug("Handling lcov-data relevant body")
    try:
        if eu.uses_condition_coverage(coverage_goal):
            return _get_condition_coverage(lcov_lines)
        if eu.uses_line_coverage(coverage_goal) or eu.uses_branch_coverage(
            coverage_goal
        ):
            return _get_line_coverage(lcov_lines, relevant_line_numbers, coverage_goal)
        raise AssertionError("Unhandled coverage goal " + coverage_goal)
    finally:
        logging.debug("Done handling lcov-data relevant body")
        logging.debug("Done extracting coverage from created tracefile")


def _create_lcov_tracefile(coverage_goal, data_file, gcov_tool="gcov"):
    output_tracefile = "current_test.info"
    data_directory = os.path.dirname(data_file)
    cmd = ["lcov", "--gcov-tool", gcov_tool]
    if eu.uses_condition_coverage(coverage_goal):
        # add coverage information about which branch conditions were taken/evaluated.
        # This option makes lcov pretty slow, so
        # we only use this option when necessary
        # for performance reasons. In addition,
        # lcov produces wrong line coverage with old versions of gcov (<= 8)
        # if this option is used
        cmd += ["--rc", "lcov_branch_coverage=1"]
    cmd += ["-c", "-d", data_directory, "--no-recursion", "-o", output_tracefile]
    eu.execute(cmd, quiet=True)
    return output_tracefile


def _compute_test_coverage_lcov(
    program_name,
    data_file,
    coverage_goal,
    branch_label_line_numbers=None,
    gcov_tool="gcov",
) -> Tuple[List[str], _CoverageComparable]:
    if not os.path.exists(data_file):
        raise FileNotFoundError(data_file)

    tracefile = _create_lcov_tracefile(coverage_goal, data_file, gcov_tool)
    return (
        [tracefile],
        _get_coverage_from_tracefile(
            program_name,
            tracefile,
            coverage_goal,
            branch_label_line_numbers,
        ),
    )


def compute_test_coverage(
    program_name,
    data_file,
    test_vector,
    next_result,
    coverage_goal,
    branch_label_line_numbers=None,
    gcov_tool="gcov",
    output_dir="output/info_files",
) -> TestCoverage:
    created_files, coverage = _compute_test_coverage_lcov(
        program_name,
        data_file,
        coverage_goal,
        branch_label_line_numbers,
        gcov_tool,
    )
    for f in created_files:
        _archive_file(f, test_vector.name, output_dir)
    return TestCoverage(program_name, {test_vector: next_result}, coverage)


def _archive_file(to_archive, test_name, output_dir):
    suffix = to_archive.split(".")[-1] if "." in to_archive else ""

    def _get_target(intermediate=""):
        return os.path.join(output_dir, test_name + intermediate + "." + suffix)

    target = _get_target()
    i = 1

    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)
    try:
        while os.path.exists(target):
            target = _get_target(f"-{i}")
            i += 1
        shutil.move(to_archive, target)
    except FileNotFoundError:
        pass
    except UnicodeEncodeError as e:
        logging.info("Can't move tracefile to %s: %s", target, e)
        file_count = len(os.listdir(target_dir))
        target = os.path.join(target_dir, f"test{file_count}.info")
        assert not os.path.exists(target), f"Going to overwrite file {target}"
        logging.info("Moved tracefile to %s", target)
        shutil.move(to_archive, target)
