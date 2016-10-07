PYTHON ?= python2.7
PWD != pwd
UNAME != uname
ifeq (${UNAME}, Linux)
	JAVA_HOME = ${PWD}/work/openjdk/build/linux-x86_64-normal-server-release/images/j2sdk-image
	JAVAC = ${PWD}/work/openjdk/build/linux-x86_64-normal-server-release/jdk/bin/javac
	JAVA_INC = ${JAVA_HOME}/include/linux
	GCC_LIB_DIR = ${PWD}/work/gcc-inst/lib64
endif
ifeq (${UNAME}, OpenBSD)
	JAVA_HOME = ${PWD}/work/openjdk/build/bsd-x86_64-normal-server-release/images/j2sdk-image
	JAVAC = ${PWD}/work/openjdk/build/bsd-x86_64-normal-server-release/jdk/bin/javac
	JAVA_INC = ${JAVA_HOME}/include/openbsd
	GCC_LIB_DIR = ${PWD}/work/gcc-inst/lib
endif

CC=${PWD}/work/gcc-inst/bin/zgcc

all: build-benchmarks build-startup
	@echo ""
	@echo "============================================================"
	@echo "Now run 'make bench-no-reboots' or 'make bench-with-reboots'"
	@echo "If you want reboots, make sure you set up the init system!"
	@echo "============================================================"

.PHONY: build-vms build-benchmarks build-krun build-startup bench clean
.PHONY: clean-benchmarks clean-krun

build-vms:
	./build.sh

build-benchmarks: build-krun
	cd benchmarks && \
		env LD_LIBRARY_PATH=${GCC_LIB_DIR} \
		CC=${CC} JAVAC=${JAVAC} ${MAKE}

build-krun: build-vms
	cd krun && env LD_LIBRARY_PATH=${GCC_LIB_DIR} CC=${CC} \
		JAVA_CPPFLAGS='"-I${JAVA_HOME}/include -I${JAVA_INC}"' \
		JAVA_LDFLAGS=-L${JAVA_HOME}/lib \
		JAVAC=${JAVAC} ENABLE_JAVA=1 ${MAKE}

build-startup: build-krun
	cd startup_runners && \
		env LD_LIBRARY_PATH=${GCC_LIB_DIR} CC=${CC} \
		JAVA_CPPFLAGS='"-I${JAVA_HOME}/include \
		-I${JAVA_HOME}/include/linux"' \
		JAVA_LDFLAGS=-L${JAVA_HOME}/lib \
		JAVAC=${JAVAC} ENABLE_JAVA=1 ${MAKE}

bench-no-reboots: build-krun build-benchmarks
	${PYTHON} krun/krun.py warmup.krun

bench-with-reboots: build-krun build-benchmarks
	${PYTHON} krun/krun.py --reboot warmup.krun

bench-startup-no-reboots: build-startup build-benchmarks
	${PYTHON} krun/krun.py startup.krun

bench-startup-with-reboots: build-startup build-benchmarks
	${PYTHON} krun/krun.py --reboot startup.krun

bench-dacapo: build-krun build-vms
	PYTHONPATH=krun/ JAVA_HOME=${JAVA_HOME} ${PYTHON} extbench/rundacapo.py
	bin/csv_to_krun_json -u "`uname -a`" -v Graal -l Java dacapo.graal.results
	bin/csv_to_krun_json -u "`uname -a`" -v HotSpot -l Java dacapo.hotspot.results

bench-octane: build-krun build-vms
	PYTHONPATH=krun/ ${PYTHON} extbench/runoctane.py
	bin/csv_to_krun_json -u "`uname -a`" -v V8 -l JavaScript octane.v8.results
	bin/csv_to_krun_json -u "`uname -a`" -v SpiderMonkey -l JavaScript octane.spidermonkey.results

# XXX target to format results.

clean: clean-benchmarks clean-krun
	rm -rf work

clean-benchmarks:
	cd benchmarks && ${MAKE} clean
	rm -rf extbench/octane/dacapo*.jar extbench/octane

clean-krun:
	cd krun && ${MAKE} clean
