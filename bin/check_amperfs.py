#!/usr/bin/env python2.7
"""
usage: check_amperfs.py <results_file> <ratio-bounds>
            <tickful-idle-threshold> <tickless-idle-threshold>
            <idle-threshold-factor>

Checks if the CPU has clocked down or entered turbo mode during Krun
benchmarking.

Arguments:
    * results_file:
        A krun results file.

    * ratio-bounds:
        Comma separated pair of allowed deviation from the target aperf/mperf
        ratio. e.g. '0.9,1.2'.

    * tickful-idle-threshold:
        Estimated time-normalised (per-second) aperf reading for a idle tickful
        CPU core.

    * tickless-idle-threshold:
        Estimated time-normalised (per-second) aperf reading for a idle
        tickless CPU core.

    * idle-threshold-factor
        Value to multiply idle-thresholds by to make the idle/busy threshold.
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


def check_amperfs(aperfs, mperfs, wcts, idle_threshold):
    assert len(aperfs) == len(mperfs) == len(wcts)

    res = AMResult()
    for aval, mval, wctval in zip(aperfs, mperfs, wcts):
        # normalise the counts to per-second readings
        norm_aval = float(aval) / wctval
        norm_mval = float(mval) / wctval
        ratio = norm_aval / norm_mval

        # Record the extents of ratio for idle/busy times
        if norm_mval < idle_threshold:
            # Idle core
            if ratio < 1.0 and ratio < res.ratio_bounds_idle[0]:
                res.ratio_bounds_idle[0] = ratio
            elif ratio > 1.0 and ratio > res.ratio_bounds_idle[1]:
                res.ratio_bounds_idle[1] = ratio
        else:
            # Busy core
            if ratio < 1.0 and ratio < res.ratio_bounds_busy[0]:
                res.ratio_bounds_busy[0] = ratio
            elif ratio > 1.0 and ratio > res.ratio_bounds_busy[1]:
                res.ratio_bounds_busy[1] = ratio
    assert res.ratio_bounds_idle[0] <= res.ratio_bounds_idle[1]
    assert res.ratio_bounds_busy[0] <= res.ratio_bounds_busy[1]
    return res


def main(data_dct, ratio_bounds, idle_threshold):
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
                    idle_threshold = idle_thresholds[0]
                else:
                    # tickless core
                    idle_threshold = idle_thresholds[1]

                res = check_amperfs(core_aperfs, core_mperfs, pexec_wcts,
                                    idle_threshold)

                # Now report errors
                if res.ratio_bounds_busy[0] < ratio_bounds[0]:
                    print("WARNING! Thottling?: key=%s, pexec=%s, core=%s, %s"
                          % (key, pexec_idx, core_idx, res))
                elif res.ratio_bounds_busy[1] > ratio_bounds[1]:
                    print("WARNING! Turbo?: key=%s, pexec=%s, core=%s, %s"
                          % (key, pexec_idx, core_idx, res))
                else:
                    assert ratio_bounds[0] <= res.ratio_bounds_busy[0]
                    assert res.ratio_bounds_busy[1] <= ratio_bounds[1]
                    if DEBUG:
                        print("ok: key=%s, pexec=%s, core=%s, %s" %
                              (key, pexec_idx, core_idx, res))
                summary.merge(res)
            pexecs_checked +=1
    print("")
    print("num proc. execs. checked: %s" % pexecs_checked)
    print("idle a/mperf count threshold: %s" % idle_threshold)
    print("busy ratio thresholds: [%s, %s]" % (ratio_bounds[0], ratio_bounds[1]))
    print("summary: %s " % summary)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)

    try:
        lo_ratio, hi_ratio = sys.argv[2].split(",")
        ratio_bounds = float(lo_ratio), float(hi_ratio)
        idle_threshold_factor = float(sys.argv[5])
        idle_thresholds = float(sys.argv[3]) * idle_threshold_factor, \
            float(sys.argv[4]) * idle_threshold_factor # tickful, tickless
    except:
        print(__doc__)
        sys.exit(1)

    data_dct = read_krun_results_file(sys.argv[1])
    main(data_dct, ratio_bounds, idle_thresholds)
