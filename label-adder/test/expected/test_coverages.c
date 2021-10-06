// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern int __VERIFIER_nondet_int();

int main() {
Goal_1:;

  int a = __VERIFIER_nondet_int();
  int x;

  if (!(a == 6) || a == 5 || a == 3) {
  Goal_3:;
  
    if (a == 3) {
    Goal_5:;
    
      x = 2;
    } else {
    Goal_6:;
    
      x = 3;
    }
    x = 3;
  } else {
  Goal_4:;
  
    x = 5;
  }

  if (a == 3) {
  Goal_7:;
  
    x = 2;
  }

  if (a == 5) {
  Goal_8:;
  
    x = 3;
  }

Goal_2:;

}
