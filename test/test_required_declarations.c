// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2020 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern char __VERIFIER_nondet_char();

typedef int FILE_example;
typedef int _FILE;
typedef int FILE0 ;
void reach_error() {}
char reach_error0() {
  reach_error();
}

void exit_ () { }
void exit0 () { }

void
strcpy0 () {}
void
strcpy_ () {}
void
_strcpy () {}



int main() {
  char a = __VERIFIER_nondet_char();
  char b = __VERIFIER_nondet_char();
  char c = __VERIFIER_nondet_char();
  if (c == 16 && a == 'a' && b == 5) {
      reach_error0();
  }
}