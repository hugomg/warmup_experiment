#! /usr/bin/env python2.7

import csv, os, sys, time
from decimal import Decimal
from krun.platform import detect_platform
from krun.util import run_shell_cmd_bench

WARMUP_DIR = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))

JAVASCRIPT_VMS = {
    "v8": "sh -c 'cd %s/extbench/octane && LD_LIBRARY_PATH=%s/krun/libkrun %s/work/v8/out/native/d8 run.js'"
          % (WARMUP_DIR, WARMUP_DIR, WARMUP_DIR),
    "spidermonkey": "sh -c 'cd %s/extbench/octane && %s/work/spidermonkey/js/src/build_OPT.OBJ/dist/bin/js run.js'"
          % (WARMUP_DIR, WARMUP_DIR)
}

ITERATIONS = 2000
PROCESSES = 10

def main():
    platform = detect_platform(None, None)
    for jsvm_name, jsvm_cmd in JAVASCRIPT_VMS.items():
        with open("octane.%s.results" % jsvm_name, 'wb') as csvf:
            sys.stdout.write("%s:" % jsvm_name)
            writer = csv.writer(csvf)
            writer.writerow(['processnum', 'benchmark'] + range(ITERATIONS))
            for process in range(PROCESSES):
                sys.stdout.write(" %s" % str(process))
                sys.stdout.flush()
                # Flush the CSV writing, and then give the OS some time
                # to write stuff out to disk before running the next process
                # execution.
                csvf.flush()
                os.fsync(csvf.fileno())
                time.sleep(3)

                stdout, stderr, rc = run_shell_cmd_bench(jsvm_cmd, platform)
                if rc != 0:
                    sys.stderr.write(stderr)
                    sys.exit(rc)
                times = None
                for line in stdout.splitlines():
                    assert len(line) > 0
                    # Lines beginning with something other than a space are the
                    # name of the next benchmark to run. Lines beginning with a
                    # space are the timings of an iteration
                    if line[0] == " ":
                        # Times are in ms, so convert to seconds (without any
                        # loss of precision).
                        times.append(str(Decimal(line.strip()) / 1000))
                    else:
                        assert times is None or len(times) == ITERATIONS
                        if times is not None:
                            writer.writerow([process, bench_name] + times)
                        bench_name = line.strip()
                        times = []
                assert len(times) == ITERATIONS
                writer.writerow([process, bench_name] + times)
            sys.stdout.write("\n")


if __name__ == '__main__':
    main()