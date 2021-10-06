<!--
This file is part of TestCov,
a robust test executor with reliable coverage measurement:
https://gitlab.com/sosy-lab/software/test-suite-validator/

SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>

SPDX-License-Identifier: Apache-2.0
-->

# Program transformation to add GOAL labels

Based on [clang libtooling](https://clang.llvm.org/docs/LibTooling.html)

## Build requirements

- git
- ninja >= 1.10
- cmake >= 3.16

## Build

Run `make`. This will clone LLVM and build the tool in directory `build/label-adder`.
To check whether it works, try:

```bash
$ build/label-adder/bin/label-adder test/programs/test.c
```

This prints the transformed program on stdout:

```C
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

  int x = __VERIFIER_nondet_int();
  if (x > 0) {
  Goal_3:;
  
    x++;
  } else {
  Goal_4:;
  
    x--;
  }
  Goal_2:;
  
}
```

## Usage options

You can provide a list of files to process.
By default, output is written to stdout.
Use parameter `--in-place` to store the transformed program in the provided input files, instead.

By default, additional debug info is written to stderr.
Use `--no-info` to avoid this.

By default, labels are added for the following syntax elements:
    - `if-stmt`: right after each if- (`if-case`) and else-statement (`else-case`)
    - `function`: at the beginning (`function-start`) and the return (`function-end`) of each function definition
    - `switch`: at the beginning of each switch-case block (`switch-case`) and the switch-default block (`switch-default`)
    - `ternary`: at the beginning of the true decision (`ternary-true`) and false decision (`ternary-false`) of ternary operators.

To deactivate some of these labels, use `--no-labels-TYPE`,
where `TYPE` is the respective name in the list above.
Examples: `--no-labels-if-stmt`, `--no-labels-function-end`.