# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

BUILD_DIR := build
PREFIX := .

build: ${BUILD_DIR}/label-adder/bin/label-adder

install: ${BUILD_DIR}/label-adder/bin/label-adder
	mkdir -p ${PREFIX}/bin
	mv $< ${PREFIX}/bin/

${BUILD_DIR}/label-adder/bin/label-adder: ${BUILD_DIR}/label-adder/CMakeCache.txt src/*
	cd ${BUILD_DIR}/label-adder \
		&& ninja label-adder

${BUILD_DIR}/label-adder/CMakeCache.txt: ${BUILD_DIR}/clang-tools-extra/label-adder/CMakeLists.txt
	mkdir -p ${BUILD_DIR}/label-adder \
		&& cd ${BUILD_DIR}/label-adder \
		&& cmake -G Ninja ../llvm -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD="X86" -DLLVM_BUILD_TOOLS=OFF


${BUILD_DIR}/clang-tools-extra/label-adder/CMakeLists.txt: src/CMakeLists.txt
	[ -e ${BUILD_DIR} ] || git clone https://github.com/llvm/llvm-project.git ${BUILD_DIR}
	cd ${BUILD_DIR} \
		&& if ! git diff --quiet; then echo "LLVM directory is dirty. Please clean it up and then retry."; exit; fi
	cd ${BUILD_DIR} && git checkout llvmorg-11.1.0
	cd ${BUILD_DIR}/clang-tools-extra \
		&& ln -s ../../src label-adder
	echo 'add_subdirectory(label-adder)' >> ${BUILD_DIR}/clang-tools-extra/CMakeLists.txt


clean:
	${RM} -rf ${BUILD_DIR}
