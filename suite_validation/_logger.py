# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
"""Central logging facility for TestCov.

The other methods in this module can only be used after 'init' has been called.
"""

import logging
import sys
from typing import Optional

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


def init(loglevel=INFO, name=__package__, logfile="testcov.log"):
    """Return the logger with the given name. loglevel and logfile"""
    # pylint: disable=W0603
    global _LOGGER, _LOGGER_SET
    # disable pylint because of a false positive
    # pylint: disable=E0601
    assert not _LOGGER_SET
    _LOGGER_SET = True
    _LOGGER = _create_logger(name, loglevel, logfile)


def critical(*args, **kwargs):
    _LOGGER.critical(*args, **kwargs)


def error(*args, **kwargs):
    _LOGGER.error(*args, **kwargs)


def exception(*args, **kwargs):
    _LOGGER.exception(*args, **kwargs)


def warning(*args, **kwargs):
    _LOGGER.warning(*args, **kwargs)


def info(*args, **kwargs):
    _LOGGER.info(*args, **kwargs)


def debug(*args, **kwargs):
    _LOGGER.debug(*args, **kwargs)


def print_progress(count: int, total: int, target=None):
    _LOGGER.print_progress(count, total, target)


def print_done(target=None):
    _LOGGER.print_done(target)


def _create_logger(name, level, logfile=None):
    delegate = logging.getLogger(name)
    delegate.setLevel(level)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(fmt=logging.BASIC_FORMAT))
    delegate.addHandler(stdout_handler)
    if logfile is not None:
        logfile_handler = logging.FileHandler(logfile)
        logfile_formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logfile_handler.setFormatter(logfile_formatter)
        delegate.addHandler(logfile_handler)
    return Logger(delegate)


class Logger:
    def __init__(self, delegate: Optional[logging.Logger] = None):
        self.log_written_since_status_update = True
        """Whether any log message has been written since the last invocation of 'print_progress'."""

        if delegate is None:
            delegate = logging.getLogger()
        self.delegate = delegate

    def print_progress(self, count: int, total: int, target=None):
        if target is None:
            # do not use sys.stderr as default value in parameter but assign
            # it dynamically, to always take the current stream sys.stderr points to
            target = sys.stderr
        digits = len(str(total))
        status_report = f"⏳ Executing tests {count:{digits}}/{total:{digits}}"
        if not self.log_written_since_status_update:
            cursor_movement = "\033[A\r"  # overwrite previous progress report
        else:
            cursor_movement = ""  # do not overwrite previous log message
        self.log_written_since_status_update = False
        print(cursor_movement + status_report, file=target, flush=True)

    @staticmethod
    def print_done(target=None):
        if target is None:
            # do not use sys.stderr as default value in parameter but assign
            # it dynamically, to always take the current stream sys.stderr points to
            target = sys.stderr
        print("✔️  Done!", file=target, flush=True)  # print newline

    def critical(self, *args, **kwargs):
        if self.is_enabled_for(logging.CRITICAL):
            self.log_written_since_status_update = True
        self.delegate.critical(*args, **kwargs)

    def error(self, *args, **kwargs):
        if self.is_enabled_for(logging.ERROR):
            self.log_written_since_status_update = True
        self.delegate.error(*args, **kwargs)

    def exception(self, *args, **kwargs):
        if self.is_enabled_for(logging.EXCEPTION):
            self.log_written_since_status_update = True
        self.delegate.exception(*args, **kwargs)

    def warning(self, *args, **kwargs):
        if self.is_enabled_for(logging.WARNING):
            self.log_written_since_status_update = True
        self.delegate.warning(*args, **kwargs)

    def info(self, *args, **kwargs):
        if self.is_enabled_for(logging.INFO):
            self.log_written_since_status_update = True
        self.delegate.info(*args, **kwargs)

    def debug(self, *args, **kwargs):
        if self.is_enabled_for(logging.DEBUG):
            self.log_written_since_status_update = True
        self.delegate.debug(*args, **kwargs)

    def is_enabled_for(self, level) -> bool:
        return self.delegate.isEnabledFor(level)


_LOGGER = Logger(logging.getLogger())
_LOGGER_SET = False
