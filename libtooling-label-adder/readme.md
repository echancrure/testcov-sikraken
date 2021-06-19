# Labeler auf Basis von LLVM-Clang-Libtooling
## Build-Anleitung

Als erstes wird ein Verzeichnis benötigt, in dem alles heruntergeladen und gebaut werden soll.

    cd GEWÜNSCHTES/VERZEICHNIS
	
Dann wird LLVM geclont

    git clone https://github.com/llvm/llvm-project.git
    
Als nächstes wird Ninja benötigt

    git clone https://github.com/martine/ninja.git
    cd ninja
    git checkout release
    ./bootstrap.py
    sudo cp ninja /usr/bin/
    cd..
    
Außerdem noch cmake

    git clone git://cmake.org/stage/cmake.git
    cd cmake
    git checkout next
    ./bootstrap
    make
    sudo make install
    cd ..

Da der Ubuntu-Standard-Linker das LLVM-Hauptprojekt nicht bauen kann, weil er mit einzelnen RAM-Spikes selbst über 64GB RAM und 64GB Swap kommt und mit Sig 9 abstürzt. Muss ein anderer Linker verwendet werden, beispielsweise der lld Linker von llvm. https://lld.llvm.org/
Damit der Standard-Linker beim bauen von lld nicht abschmiert, wird bei make die Anzahl der Jobs mit -j auf 1 festgelegt. Beim bauen von LLVM selbst mithilfe des lld-Linkers lässt sich das bauen dann wieder parallelisieren, wodurch es bei einer CPU mit vielen Kernen dann auch deutlich schneller geht.

    cd llvm-project
    mkdir lldbuild
    cd lldbuild
    cmake -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_PROJECTS=lld -DCMAKE_INSTALL_PREFIX=/usr/local ../llvm-project/llvm
    make install -j 1
    cd ..

Im llvm-project/bin Verzeichnis befindet sich nun der lld Linker. Der Ubuntu-Standard-Linker befindet sich in `/usr/bin/ld` dieser muss durch den lld Linker ausgetauscht werden.

    ln -s /lldbuild/bin/ld.lld /usr/bin/ld

Nun kann llvm gebaut werden

    mkdir build
    cd build
    cmake -G Ninja ../llvm -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" -DLLVM_BUILD_TESTS=ON 
    ninja
    ninja check
    ninja clang-test
    ninja install

Abschließend muss noch clang als sein eigener Compiler gesetzt werden.

    ccmake ../llvm

Dann 't' drücken für den erweiterten Modus und `CMAKE_CXX_COMPILER` auf `/usr/bin/clang++` setzen.
Falls clang++ nicht in /usr/bin sein sollte, die binary aus dem build/bin Ordner nach /usr/bin rüber kopieren

    cd ..
    
In den clang-tools-extra Ordner wechseln und ein Verzeichnis für den Labeler hinzufügen


    cd clang-tools-extra
    mkdir labeler
    echo 'add_subdirectory(labeler)' >> CMakeLists.txt
    cd ..

In diesen Ordner die Dateien vom Labeler rein packen

Abschließend wieder in den build Ordner und den Labeler bauen

	cd build
	ninja

und voila im build/bin ordner befindet sich die binary für den Labeler.
einfach mit `labeler dateiname.cpp` aufrufen und fertig.

Bei jedem abändern vom Code des Labelers einfach `ninja` neu aufrufen und die binary wird neu gebaut.

## Labeler Optionen

Der Aufruf läuft über  `labeler [Optionen] datei.cpp`, es kann auch eine Liste von Dateien angegeben werden.
Standardmäßig wird alles in Standard-Out ausgegeben, um hingegen alle Dateien einfach zu überschreiben, so dass die Labels in diesen drinnen sind `--in-place` verwenden.
Falls die ursprünglichen Dateien nicht modifiziert werden sollen, einfach die Dateien in ein neues Verzeichnis kopieren und dort den labeler mit `--in-place` aufrufen.
Falls es nicht gewünscht ist, dass zusätzliche Informationen, wie der z.B. AST in stderr ausgegeben werden `--no-info` mit angeben.
Um das Labeln von einzelnen Syntax-Elementen zu deaktivieren:

    --no-labels-if-stmt
    --no-labels-function
    --no-labels-switch
    --no-labels-ternary
    
Es können auch einzelne Teil-Element, wie Labels am Funktions-Anfang/Ende deaktiviert werden:

    --no-labels-function-start
    --no-labels-function-end
    
    --no-labels-if-case
    --no-labels-else-case
    
    --no-labels-switch-case
    --no-labels-switch-default
    
    --no-labels-ternary-true
    --no-labels-ternary-false

## Projekt-Struktur
|Dateie(en)|Funktion|
|--|--|
|Includes|Alle Bibliotheken, die eingebunden werden|
|LabelerMain|Optionen definieren und einlesen, Tool starten|
|OptionsStruct|Ein Struct mit Booleans für alle Optionen|
|LabelerFrontEndActionFactory|Implementierung von Libtoolings Factory, mit welcher pro Source-Datei einzelne Frontend-Actions erstellt werden.|
|LabelerFrontendAction|Implementierung von Libtoolings FrontendAction, sozusagen die Main-Klasse für die Verarbeitung einer einzelnen Source-Datei. Zuerst wird CreateASTConsumer aufgerufen. Der Consumer wird gestartet und wenn er fertig ist wird EndSourceFileAction aufgerufen.|
|LabelerASTConsumer|Der Consumer ließt den AST einer einzelnen Source-Datei ein und ruft dann bei jedem eingelesenen Syntax-Element die jeweiligen Methoden des Visitors auf.|
|LabelerASTVisitor|Der Visitor wird für die jeweiligen AST-Elemente aufgerufen, baut den Source-Code um, so dass Labels eingefügt werden. Z.b. One-Liner zu Compound-Statements und Ternary zu If-Statements und baut die Labels ein, wenn gewünscht.|

