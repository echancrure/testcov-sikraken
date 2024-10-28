// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2020 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0
#include <stdint.h>

#define INT128_MAX (__int128)(((unsigned __int128) 1 << ((sizeof(__int128) * __CHAR_BIT__) - 1)) - 1)
#define INT128_MIN (-INT128_MAX - 1)
#define UINT128_MAX ((2 * (unsigned __int128) INT128_MAX) + 1)

extern __int128_t __VERIFIER_nondet_int128();

int main() {
  __int128_t x = __VERIFIER_nondet_int128();
  if (x == INT128_MAX) {
    return 1;
  }
  if (x == INT128_MIN) {
    return 1;
  }
  if (x == 0) {
    return 1;
  }
  return 0;
}