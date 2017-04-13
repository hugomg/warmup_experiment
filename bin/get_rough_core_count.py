#!/usr/bin/env python2.7
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from warmup.krun_results import read_krun_results_file


BUSY_APERF_THRESHOLD = 1000000000


def mean(xs):
    assert len(xs), "can't mean a zero length list"
    return sum(xs) / len(xs)


def get_norm_mean_amperfs(aperfs, mperfs, wcts):
    assert len(aperfs) == len(mperfs) == len(wcts)
    aperfs_norm = [float(aval) / wctval for aval, wctval in zip(aperfs, wcts)]
    mperfs_norm = [float(mval) / wctval for mval, wctval in zip(mperfs, wcts)]

    all_idle = all([x > BUSY_APERF_THRESHOLD for x in aperfs_norm])
    all_busy = all([x <= BUSY_APERF_THRESHOLD for x in aperfs_norm])
    if not (all_idle or all_busy):
        print("WARNING: possible core migration")

    return  mean(aperfs_norm), mean(mperfs_norm)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: check_amperfs.py <results_file> <key>:<pexecs>, ...")
        sys.exit(1)
    data_dct = read_krun_results_file(sys.argv[1])
    spec_args = sys.argv[2:]


    idle_tickful_means = []
    idle_tickless_means = []
    busy_tickful_means = []
    busy_tickless_means = []
    for arg in sys.argv[2:]:
        bench, vm, variant, pexec_idxs = arg.split(":")
        key = "%s:%s:%s" % (bench, vm, variant)
        pexec_idxs = [int(x) for x in pexec_idxs.split(",")]

        key_wcts = data_dct["wallclock_times"][key]
        key_aperfs = data_dct["aperf_counts"][key]
        key_mperfs = data_dct["mperf_counts"][key]

        for pexec_idx in pexec_idxs:
            print("pexec: %d" % pexec_idx)
            pexec_wcts = key_wcts[pexec_idx]
            pexec_aperfs = key_aperfs[pexec_idx]
            pexec_mperfs = key_mperfs[pexec_idx]
            assert len(pexec_aperfs) == len(pexec_mperfs)

            busy_core = []
            for core_idx in xrange(len(pexec_aperfs)):
                core_aperfs = pexec_aperfs[core_idx]
                core_mperfs = pexec_mperfs[core_idx]
                mean_aperf_norm, mean_mperf_norm = \
                    get_norm_mean_amperfs(core_aperfs, core_mperfs, pexec_wcts)

                if mean_aperf_norm > BUSY_APERF_THRESHOLD:
                    busy_core.append(core_idx)
                    print("  core: %d (BUSY)" % core_idx)
                    if core_idx == 0:
                        busy_tickful_means.append(mean_aperf_norm)
                    else:
                        busy_tickless_means.append(mean_aperf_norm)
                else:
                    print("  core: %d (IDLE)" % core_idx)
                    if core_idx == 0:
                        idle_tickful_means.append(mean_aperf_norm)
                    else:
                        idle_tickless_means.append(mean_aperf_norm)
                print("    mean norm aperf: %f" % mean_aperf_norm)
                print("    mean norm mperf: %f" % mean_mperf_norm)


            if len(busy_core) != 1:
                print("WARNING: not exactly one busy core!")

    print("mean norm tickful idle aperf : %f" % mean(idle_tickful_means))
    print("mean nomm tickless idle aperf: %f" % mean(idle_tickless_means))
    print("mean norm tickful busy aperf : %f" % mean(busy_tickful_means))
    print("mean nomm tickless busy aperf: %f" % mean(busy_tickless_means))
