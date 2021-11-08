// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

extern int __VERIFIER_nondet_int();
void __assert_fail(const char *, const char *, unsigned int,
                          const char *) __attribute__((__nothrow__, __leaf__))
__attribute__((__noreturn__));

void reach_error(){__assert_fail("0", "test_assert_fail.c", 14, "example-fail");}
void reach_error2(){
  __assert_fail("0", "test_assert_fail.c", 16, "example-fail");
}
void reach_error3() { __assert_fail("0", "test_assert_fail.c", 18, "example-fail");
}

int main() {
  int x = __VERIFIER_nondet_int();
  if (x > 0) {
    x++;__assert_fail("0", "test_assert_fail.c", 24, "example-fail");
  }
  if (x == -1) {__assert_fail("0", "test_assert_fail.c", 27, "example-fail");}
  if (x == -2)__assert_fail("0", "test_assert_fail.c", 28, "example-fail");
  if (x == -3) {reach_error();}
  if (x == -4) {reach_error2();}
  if (x == -5)
    reach_error3();
  else
__assert_fail("0", "test_assert_fail.c", 30, "example-fail");

}
