

labeler: labeler-build/build/bin/labeler

install-labeler: labeler
	cp labeler-build/build/bin/labeler lib/bin/labeler

labeler-build/build/bin/labeler: labeler-build/build/CMakeCache.txt
	cd labeler-build/build \
		&& ninja labeler

labeler-build/build/CMakeCache.txt: labeler-build/clang-tools-extra/labeler/CMakeLists.txt
	mkdir -p labeler-build/build \
		&& cd labeler-build/build \
		&& cmake -G Ninja ../llvm -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD="X86" -DLLVM_BUILD_TOOLS=OFF


labeler-build/clang-tools-extra/labeler/CMakeLists.txt: labeler/CMakeLists.txt
	[ -e labeler-build ] || git clone https://github.com/llvm/llvm-project.git labeler-build
	cd labeler-build \
		&& git checkout llvmorg-11.1.0
	cd labeler-build/clang-tools-extra \
		&& ln -s ../../labeler labeler
	echo 'add_subdirectory(labeler)' >> labeler-build/clang-tools-extra/CMakeLists.txt


clean:
	rm -rf labeler-build
