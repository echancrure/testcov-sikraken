// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2020 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern void __assert_fail (const char *__assertion, const char *__file,
      unsigned int __line, const char *__function)
     __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__noreturn__));
extern void __assert_perror_fail (int __errnum, const char *__file,
      unsigned int __line, const char *__function)
     __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__noreturn__));
extern void __assert (const char *__assertion, const char *__file, int __line)
     __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__noreturn__));

extern char __VERIFIER_nondet_char();

void reach_error() {
Goal_1:;
 ((void) sizeof ((0) ? 1 : 0), __extension__ ({ if (0) {
Goal_3:;
} else {
Goal_4:;
__assert_fail ("0", "byte_add-1.c", 3, __extension__ __PRETTY_FUNCTION__);
}
 }));
Goal_2:;
 }

int main() {
Goal_5:;

  char a = __VERIFIER_nondet_char();
  char b = __VERIFIER_nondet_char();
  char c = __VERIFIER_nondet_char();

  while (a == 'a' && b == 5 && c == 16) reach_error();
  Goal_6:;
  
}
