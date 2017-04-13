#!/usr/bin/env python2.7

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from warmup.krun_results import read_krun_results_file

# debug bits
DEBUG = False
if os.environ.get("AM_DEBUG"):
    DEBUG = True


# Any A/MPERF below this value is considered an idle core.
# An idle core is in the low millions on our machines.
IDLE_AMPERF_COUNT_THRESHOLD = 20 * 1000000

# allowable deviation from ratio of 1.0 when busy
BUSY_ERROR_THESHOLD = 0.025
BUSY_ERROR_LO_BOUND = 1.0 - BUSY_ERROR_THESHOLD
BUSY_ERROR_HI_BOUND = 1.0 + BUSY_ERROR_THESHOLD


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


def check_amperfs(aperfs, mperfs, wcts):
    assert len(aperfs) == len(mperfs) == len(wcts)

    res = AMResult()
    for aval, mval, wctval in zip(aperfs, mperfs, wcts):
        # normalise the counts to per-second readings
        norm_aval = float(aval) / wctval
        norm_mval = float(mval) / wctval
        ratio = norm_aval / norm_mval

        # Record the extents of ratio for idle/busy times
        if norm_mval < IDLE_AMPERF_COUNT_THRESHOLD:
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


def main(data_dct):
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
                res = check_amperfs(core_aperfs, core_mperfs, pexec_wcts)

                # Now report errors
                if res.ratio_bounds_busy[0] < BUSY_ERROR_LO_BOUND:
                    print("WARNING! Thottling?: key=%s, pexec=%s, core=%s, %s"
                          % (key, pexec_idx, core_idx, res))
                elif res.ratio_bounds_busy[1] > BUSY_ERROR_HI_BOUND:
                    print("WARNING! Turbo?: key=%s, pexec=%s, core=%s, %s"
                          % (key, pexec_idx, core_idx, res))
                else:
                    assert BUSY_ERROR_LO_BOUND <= res.ratio_bounds_busy[0]
                    assert res.ratio_bounds_busy[1] <= BUSY_ERROR_HI_BOUND
                    if DEBUG:
                        print("ok: key=%s, pexec=%s, core=%s, %s" %
                              (key, pexec_idx, core_idx, res))
                summary.merge(res)
            pexecs_checked +=1
    print("num proc. execs. checked: %s" % pexecs_checked)
    print("idle a/mperf count threshold: %s" % IDLE_AMPERF_COUNT_THRESHOLD)
    print("busy ratio thresholds: [%s, %s]" % (BUSY_ERROR_LO_BOUND, BUSY_ERROR_HI_BOUND))
    print("summary: %s " % summary)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_amperfs.py <results_file>")
        sys.exit(1)

    data_dct = read_krun_results_file(sys.argv[1])
    main(data_dct)
