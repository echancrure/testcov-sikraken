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
void reach_error() 
Goal_2:;
{
Goal_1:;
}
char reach_error0() {
Goal_3:;

  reach_error();
  Goal_4:;
  
}

void exit_ () {
Goal_5:;

Goal_6:;
 }
void exit0 () {
Goal_7:;

Goal_8:;
 }

void
strcpy0 () 
Goal_10:;
{
Goal_9:;
}
void
strcpy_ () 
Goal_12:;
{
Goal_11:;
}
void
_strcpy () 
Goal_14:;
{
Goal_13:;
}



int main() {
Goal_15:;

  char a = __VERIFIER_nondet_char();
  char b = __VERIFIER_nondet_char();
  char c = __VERIFIER_nondet_char();
  if (c == 16 && a == 'a' && b == 5) {
  Goal_17:;
  
      reach_error0();
  }
  Goal_16:;
  
}