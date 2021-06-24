

labeler:
	git clone https://github.com/llvm/llvm-project.git
	cd llvm-project \
		&& git checkout llvmorg-11.1.0
	cd llvm-project/clang-tools-extra \
		&& ln -s ../../labeler labeler
	mkdir llvm-project/build \
		&& cd llvm-project/build \
		&& cmake -G Ninja ../llvm -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD="X86" -DLLVM_BUILD_TOOLS=OFF
		&& ninja labeler


clean:
  rm -rf build llvm-project
