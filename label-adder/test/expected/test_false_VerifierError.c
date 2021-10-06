// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern char __VERIFIER_nondet_char();
extern void __VERIFIER_error();

int main() {
Goal_1:;

  char a = __VERIFIER_nondet_char();
  char b = __VERIFIER_nondet_char();
  char c = __VERIFIER_nondet_char();

  if (a == 'a' && b == 5 && c == 16) {
  Goal_3:;
  
    __VERIFIER_error();
  }
  Goal_2:;
  
}
