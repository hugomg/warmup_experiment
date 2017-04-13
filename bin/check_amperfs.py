#!/usr/bin/env python2.7
"""
usage: check_amperfs.py <results_file> <aperf/mperf-ratio-bounds>
            <tickful-busy-threshold> <tickless-busy-threshold>
            <busy-threshold-factor>

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

    * busy-threshold-factor
        Value to divide busy-thresholds by to make the busy threshold.
"""


import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from warmup.krun_results import read_krun_results_file

# debug bits
DEBUG = False
if os.environ.get("AM_DEBUG"):
    DEBUG = True


class AMResult(object):
    def __init__(self):
        self.ratio_bounds_idle = [1.0, 1.0]
        self.ratio_bounds_busy = [1.0, 1.0]

    def __str__(self):
        return "idle=%s, busy=%s" % \
            (self.ratio_bounds_idle, self.ratio_bounds_busy)

    def merge(self, other):
        """Merge the intervals of two AMResults"""

        self.ratio_bounds_idle = [
            min(self.ratio_bounds_idle[0], other.ratio_bounds_idle[0]),
            max(self.ratio_bounds_idle[1], other.ratio_bounds_idle[1]),
        ]
        self.ratio_bounds_busy = [
            min(self.ratio_bounds_busy[0], other.ratio_bounds_busy[0]),
            max(self.ratio_bounds_busy[1], other.ratio_bounds_busy[1]),
        ]


MIGRATION_LOOKBACK = 9
def recently_migrated(aperfs, iter_idx, busy_threshold):
    for i in xrange(1, MIGRATION_LOOKBACK + 1):
        prior_aperf = aperfs[iter_idx - i]
        if prior_aperf < busy_threshold:
            return True
    return False


def check_amperfs(aperfs, mperfs, wcts, busy_threshold, ratio_bounds,
                  key, pexec_idx, core_idx):
    assert len(aperfs) == len(mperfs) == len(wcts)

    res = AMResult()
    iter_idx = 0
    for aval, mval, wctval in zip(aperfs, mperfs, wcts):
        # normalise the counts to per-second readings
        norm_aval = float(aval) / wctval
        norm_mval = float(mval) / wctval
        ratio = norm_aval / norm_mval

        # Record the extents of ratio for idle/busy times for the summary
        if norm_aval < busy_threshold:
            # Idle core
            if ratio < 1.0 and ratio < res.ratio_bounds_idle[0]:
                res.ratio_bounds_idle[0] = ratio
            if ratio > 1.0 and ratio > res.ratio_bounds_idle[1]:
                res.ratio_bounds_idle[1] = ratio
        else:
            # Busy core
            if ratio < 1.0 and ratio < res.ratio_bounds_busy[0]:
                res.ratio_bounds_busy[0] = ratio
            if ratio > 1.0 and ratio > res.ratio_bounds_busy[1]:
                res.ratio_bounds_busy[1] = ratio

            if ratio < ratio_bounds[0]:
                if not recently_migrated(aperfs, iter_idx, busy_threshold):
                    print("WARNING! Thottling?: key=%s, pexec=%s, iter=%s core=%s, ratio=%s"
                          % (key, pexec_idx, iter_idx, core_idx, ratio))
            elif ratio > ratio_bounds[1]:
                print("WARNING! Turbo?: key=%s, pexec=%s, iter=%s core=%s, ratio=%s"
                      % (key, pexec_idx, iter_idx, core_idx, ratio))
        iter_idx += 1
    assert res.ratio_bounds_idle[0] <= res.ratio_bounds_idle[1]
    assert res.ratio_bounds_busy[0] <= res.ratio_bounds_busy[1]
    return res


def main(data_dct, ratio_bounds, busy_threshold):
    pexecs_checked = 0
    summary = AMResult()

    for key, key_wcts in data_dct["wallclock_times"].iteritems():
        key_aperfs = data_dct["aperf_counts"][key]
        key_mperfs = data_dct["mperf_counts"][key]
        assert len(key_aperfs) == len(key_mperfs) == len(key_wcts), \
            "pexec count should match"

        for pexec_idx in xrange(len(key_aperfs)):
            pexec_aperfs = key_aperfs[pexec_idx]
            pexec_mperfs = key_mperfs[pexec_idx]
            pexec_wcts = key_wcts[pexec_idx]
            assert len(pexec_aperfs) == len(pexec_mperfs), \
                "core count should match for a/mperfs"

            for core_idx in xrange(len(pexec_aperfs)):
                core_aperfs = pexec_aperfs[core_idx]
                core_mperfs = pexec_mperfs[core_idx]
                if core_idx == 0:
                    # tickful core
                    busy_threshold = busy_thresholds[0]
                else:
                    # tickless core
                    busy_threshold = busy_thresholds[1]

                res = check_amperfs(core_aperfs, core_mperfs, pexec_wcts,
                                    busy_threshold, ratio_bounds,
                                    key, pexec_idx, core_idx)
                summary.merge(res)
            pexecs_checked +=1
    print("")
    print("num proc. execs. checked: %s" % pexecs_checked)
    print("busy a/mperf count threshold: %s" % busy_threshold)
    print("aperf/mperf ratio thresholds: [%s, %s]" % (ratio_bounds[0], ratio_bounds[1]))
    print("summary: %s " % summary)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)

    try:
        lo_ratio, hi_ratio = sys.argv[2].split(",")
        ratio_bounds = float(lo_ratio), float(hi_ratio)
        busy_threshold_factor = float(sys.argv[5])
        busy_thresholds = float(sys.argv[3]) / busy_threshold_factor, \
            float(sys.argv[4]) / busy_threshold_factor # tickful, tickless
    except:
        print(__doc__)
        sys.exit(1)

    data_dct = read_krun_results_file(sys.argv[1])
    main(data_dct, ratio_bounds, busy_thresholds)
