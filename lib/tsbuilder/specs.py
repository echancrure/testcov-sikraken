# This file is part of the Test-Comp test format,
# an exchange format for test suites:
# https://gitlab.com/sosy-lab/software/test-format
#
# Copyright (C) 2018  Dirk Beyer
# SPDX-FileCopyrightText: 2018-2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Constants for common test specifications."""

COVER_ERROR = "CHECK( init(main()), LTL(G ! call(__VERIFIER_error())) )"
"""Specification that __VERIFIER_error should never be reached"""

BRANCH_COVERAGE = "CHECK( init(main()), FQL(cover EDGES(@DECISIONEDGE)) )"
"""Specification that all branches should be covered (branch coverage)"""

CONDITION_COVERAGE = "CHECK( init(main()), FQL(cover EDGES(@CONDITIONEDGE)) )"
"""Specification that all condition outcomes should be covered (condition coverage)"""

STATEMENT_COVERAGE = "CHECK( init(main()), FQL(cover EDGES(@BASICBLOCKENTRY)) )"
"""Specification that all statemens should be covered (statement coverage)"""
