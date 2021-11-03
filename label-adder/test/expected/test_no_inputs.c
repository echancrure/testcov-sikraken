// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

int main() {
Goal_1:;

  int x = 1;
  if (x > 0) {
  Goal_3:;
  
    x++;
  } else {
  Goal_4:;
  
    x--;
  }
  Goal_2:;
  
}
