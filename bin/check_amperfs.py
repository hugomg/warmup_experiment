#!/usr/bin/env python2.7
"""
usage: check_amperfs.py <results_file> <aperf/mperf-ratio-bounds>
            <tickful-busy-threshold> <tickless-busy-threshold>
            <busy-threshold-factor> <migration-lookback>

Checks if the CPU has clocked down or entered turbo mode during Krun
benchmarking. A core is considered idle when the aperf value is less than the
estimated busy threshold divided by the busy threshold factor. Busy core
aperf/mperf ratios are then checked to be within the specified bouunds.

Arguments:
    * results_file:
        A krun results file.

    * ratio-bounds:
        Comma separated pair of allowed deviation from the target aperf/mperf
        ratio of 1. e.g. '0.9,1.2'.

    * tickful-busy-threshold:
        Estimated time-normalised (per-second) aperf reading for a idle tickful
        CPU core.

    * tickless-busy-threshold:
        Estimated time-normalised (per-second) aperf reading for a idle
        tickless CPU core.

    * busy-threshold-factor:
        Value to divide busy-thresholds by to make the busy threshold.

    * migration-lookback:
      Number of iterations to look back for migration. Dodgy aperf/mperf ratios
      will be ignored if the fall in this interval.
"""


import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from warmup.krun_results import read_krun_results_file


def recently_migrated(aperfs, iter_idx, busy_threshold, migration_lookback):
    for i in xrange(1, migration_lookback + 1):
        prior_aperf = aperfs[iter_idx - i]
        if prior_aperf < busy_threshold:
            return True
    return False


BAD_COUNT = 0
BAD_OUTLIER_COUNT = 0
BAD_PEXECS = 0
def check_amperfs(aperfs, mperfs, wcts, busy_threshold, ratio_bounds,
                  key, pexec_idx, core_idx, migration_lookback, cycles, all_cores_aperfs, all_cores_mperfs, all_cores_cycles, outliers):
    assert len(aperfs) == len(mperfs) == len(wcts)
    global BAD_COUNT, BAD_OUTLIER_COUNT

    iter_idx = 0
    bad_pexec = False
    for aval, mval, wctval in zip(aperfs, mperfs, wcts):
        # normalise the counts to per-second readings
        norm_aval = float(aval) / wctval
        norm_mval = float(mval) / wctval
        ratio = norm_aval / norm_mval

        if norm_aval > busy_threshold:
            # Busy core
            if ratio < ratio_bounds[0]:
                #if not recently_migrated(aperfs, iter_idx, busy_threshold,
                #                         migration_lookback):
                if True:
                    bad_pexec = True
                    BAD_COUNT += 1
                    if iter_idx in outliers:
                        BAD_OUTLIER_COUNT += 1
                    else:
                        print("WARNING! Thottling?: "
                              "key=%s, pexec=%s, iter=%s core=%s, ratio=%s"
                      % (key, pexec_idx, iter_idx, core_idx, ratio))
                    #start_idx = iter_idx - 15
                    #stop_idx = iter_idx + 1
                    #for core in 0,1,2,3:
                    #    print("core %d" % core)
                    #    sys.stdout.write("cc: ")
                    #    for i in xrange(start_idx, stop_idx):
                    #        star = " "
                    #        if iter_idx == i and core == core_idx:
                    #            star = ">"
                    #        sys.stdout.write("%s%10d  " % (star, all_cores_cycles[core][i]))
                    #    print("")
                    #    sys.stdout.write("am: ")
                    #    for i in xrange(start_idx, stop_idx):
                    #        star = " "
                    #        if iter_idx == i and core == core_idx:
                    #            star = ">"
                    #        anorm = float(all_cores_aperfs[core][i]) / wcts[i]
                    #        mnorm = float(all_cores_mperfs[core][i]) / wcts[i]
                    #        rt = anorm/mnorm
                    #        sys.stdout.write("%s%10.2f  " % (star, rt))
                    #    sys.stdout.write("\nwc: ")
                    #    for i in xrange(start_idx, stop_idx):
                    #        star = " "
                    #        if iter_idx == i and core == core_idx:
                    #            star = ">"
                    #        sys.stdout.write("%s%10.2f  " % (star, wcts[i]))
                    #    print("\n")
            elif ratio > ratio_bounds[1]:
                print("WARNING! Turbo?: "
                      "key=%s, pexec=%s, iter=%s core=%s, ratio=%s"
                      % (key, pexec_idx, iter_idx, core_idx, ratio))
        iter_idx += 1
    return bad_pexec


def main(data_dct, ratio_bounds, busy_threshold, migration_lookback):
    global BAD_COUNT, BAD_OUTLIER_COUNT, BAD_PEXECS
    pexecs_checked = 0
    for key, key_wcts in data_dct["wallclock_times"].iteritems():
        key_aperfs = data_dct["aperf_counts"][key]
        key_mperfs = data_dct["mperf_counts"][key]
        key_cycles = data_dct["core_cycle_counts"][key]
        key_outliers = data_dct["all_outliers"][key]
        assert len(key_aperfs) == len(key_mperfs) == len(key_wcts), \
            "pexec count should match"

        for pexec_idx in xrange(len(key_aperfs)):
            bad_pexec = False
            pexec_aperfs = key_aperfs[pexec_idx]
            pexec_mperfs = key_mperfs[pexec_idx]
            pexec_wcts = key_wcts[pexec_idx]
            pexec_cycles = key_cycles[pexec_idx]
            pexec_cycles = key_cycles[pexec_idx]
            pexec_outliers = key_outliers[pexec_idx]
            assert len(pexec_aperfs) == len(pexec_mperfs), \
                "core count should match for a/mperfs"

            for core_idx in xrange(len(pexec_aperfs)):
                core_aperfs = pexec_aperfs[core_idx]
                core_mperfs = pexec_mperfs[core_idx]
                core_cycles = pexec_cycles[core_idx]
                if core_idx == 0:
                    # tickful core
                    busy_threshold = busy_thresholds[0]
                else:
                    # tickless core
                    busy_threshold = busy_thresholds[1]

                bad_core = check_amperfs(core_aperfs, core_mperfs, pexec_wcts,
                                    busy_threshold, ratio_bounds,
                                    key, pexec_idx, core_idx,
                                    migration_lookback, core_cycles,
                                    pexec_aperfs, pexec_mperfs, pexec_cycles,
                                    pexec_outliers)
                if bad_core and not bad_pexec:
                    bad_pexec = True
            if bad_pexec:
                BAD_PEXECS += 1
            pexecs_checked += 1

    print("Violations: %s" % BAD_COUNT)
    print("Of which outliers: %s" % BAD_OUTLIER_COUNT)
    print("# Pexecs with violations: %s" % BAD_PEXECS)
    print("# Pexecs examined: %s" % pexecs_checked)


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(1)

    try:
        lo_ratio, hi_ratio = sys.argv[2].split(",")
        ratio_bounds = float(lo_ratio), float(hi_ratio)
        busy_threshold_factor = float(sys.argv[5])
        busy_thresholds = float(sys.argv[3]) / busy_threshold_factor, \
            float(sys.argv[4]) / busy_threshold_factor  # tickful, tickless
        migration_lookback = int(sys.argv[6])
    except:
        print(__doc__)
        sys.exit(1)

    data_dct = read_krun_results_file(sys.argv[1])
    main(data_dct, ratio_bounds, busy_thresholds, migration_lookback)
