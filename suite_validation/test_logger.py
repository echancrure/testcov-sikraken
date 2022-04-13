# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2022 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import pytest

import suite_validation._logger as logging


@pytest.fixture(autouse=True)
def reset_logging():
    # pylint: disable=W0212
    logging._LOGGER = None
    logging._LOGGER_SET = False


def test_writes_to_logfile(tmp_path):
    testmessage = "Test message"
    logfile = tmp_path / "test.log"

    logging.init(logging.INFO, "test", logfile=str(logfile))
    logging.info(testmessage)

    assert logfile.exists()
    assert testmessage in logfile.read_text()


def test_writes_to_stderr(capsys):
    testmessage = "Some foo message"

    logging.init(logging.INFO, "test", logfile=None)
    logging.info(testmessage)

    assert testmessage in capsys.readouterr().err


def test_writes_progress_initial(capsys):
    count = 1
    total = 10
    expected = f"{count}/{total}"

    logging.init(logging.INFO, "test", logfile=None)
    logging.print_progress(count, total)

    output = capsys.readouterr().err
    assert expected in output


def test_writes_progress_continuous(capsys):
    count = 5
    total = 10
    pattern = "/10\n\033[A\r"
    expected = f"{count}/{total}"

    logging.init(logging.INFO, "test", logfile=None)
    for i in range(1, count + 1):
        logging.print_progress(i, total)
    output = capsys.readouterr().err

    assert expected in output
    assert (
        output.count(pattern) == count - 1
    ), "Progress should overwrite itself, but no cursor movement recognized"


def test_writes_progress_no_log_overwrite(capsys):
    count = 5
    total = 10
    cursor_up = "\033[A"
    carriage_return = "\r"
    expected = f"{count}/{total}"
    logmessage = "Message #1"

    logging.init(logging.INFO, "test", logfile=None)
    logging.print_progress(1, total)
    logging.info(logmessage)
    logging.print_progress(count - 1, total)
    logging.print_progress(count, total)
    output = capsys.readouterr().err.strip()
    output_lines = output.split("\n")
    line_after_logmessage = output_lines[-2]
    assert (
        f"{count-1}/10" in line_after_logmessage
    ), "The test selected a wrong index for the line right after the log message"

    assert expected in output
    assert logmessage in output
    assert (
        cursor_up not in line_after_logmessage
        and carriage_return not in line_after_logmessage
    )
