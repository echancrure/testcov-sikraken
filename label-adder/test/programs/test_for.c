// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern char __VERIFIER_nondet_char();

void reach_error() {}

int main() {
  char a = __VERIFIER_nondet_char();

  int i;
  for(i=0;i<10;i++){a++;}
  for ( i = 0; i < 10 ;) 
  {
	  a++ ;
  }
}
