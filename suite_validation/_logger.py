# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0
"""Central logging facility for TestCov"""

import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


LOGGER = None


def init(level, logfile):
    # pylint: disable=W0603
    global LOGGER
    LOGGER = _create_logger(level, logfile)


def _create_logger(level, logfile):
    logger = logging.getLogger()
    logger.setLevel(level)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(fmt=logging.BASIC_FORMAT))
    logger.addHandler(stdout_handler)
    logfile_handler = logging.FileHandler(logfile)
    logfile_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    )
    logfile_handler.setFormatter(logfile_formatter)
    logger.addHandler(logfile_handler)
    return logger


def critical(*args, **kwargs):
    LOGGER.critical(*args, **kwargs)


def error(*args, **kwargs):
    LOGGER.error(*args, **kwargs)


def exception(*args, **kwargs):
    LOGGER.exception(*args, **kwargs)


def warning(*args, **kwargs):
    LOGGER.warning(*args, **kwargs)


def info(*args, **kwargs):
    LOGGER.info(*args, **kwargs)


def debug(*args, **kwargs):
    LOGGER.debug(*args, **kwargs)
