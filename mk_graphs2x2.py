#!/usr/bin/env python2.7
"""
usage:
mk_graphs2x2.py <config file1> <machine name1> <config file2> <machine name2>
"""

import sys
import json
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('ggplot')

# Set figure size for plots
plt.figure(tight_layout=True)

# Set font size
font = {
    'family': 'sans',
    'weight': 'regular',
    'size': '12',
}
matplotlib.rc('font', **font)

ROLLING_AVG = 200
STDDEV_FACTOR = 2.575
LINES_PERCENT = 1


def usage():
    print(__doc__)
    sys.exit(1)


def rolling_window(a, window):
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


def main(data_dcts, mch_names):
    keys = sorted(data_dcts[0]["data"].keys())
    for key in keys:
        # Assume data in json files have the same keys
        bench, vm, variant = key.split(":")

        # Ignore warmup!
        executions1 = data_dcts[0]["data"][key]
        executions2 = data_dcts[1]["data"][key]

        interactive(key, [executions1, executions2], mch_names)


def draw_runseq_subplot(axis, data, title):
    axis.plot(data)
    avg = np.convolve(
        data, np.ones((ROLLING_AVG,))/ROLLING_AVG)[ROLLING_AVG-1:-ROLLING_AVG]
    window = rolling_window(np.array(data), ROLLING_AVG)
    rolling_stddev = np.std(window, 1)
    pad = ROLLING_AVG / 2

    avg = np.mean(window, 1)

    upper_std_dev = avg + STDDEV_FACTOR * rolling_stddev
    upper_std_dev = np.insert(upper_std_dev, 0, [None] * pad)

    lower_std_dev = avg - STDDEV_FACTOR * rolling_stddev
    lower_std_dev = np.insert(lower_std_dev, 0, [None] * pad)

    # Must come after std_dev lines built
    avg = np.insert(avg, 0, [None] * pad)

    axis.plot(lower_std_dev)
    axis.plot(upper_std_dev)
    axis.plot(avg)

    #axis.plot(avg * (1 + LINES_PERCENT / 100.0))
    #axis.plot(avg * (1 - LINES_PERCENT / 100.0))

    axis.set_title(title)
    axis.set_xlabel("Iteration")
    axis.set_ylabel("Time(s)")


def interactive(key, executions, mch_names):
    assert len(executions) == 2
    assert len(executions[0]) == 2
    assert len(executions[1]) == 2
    n_execs = 2
    n_files = 2  # number of json files

    fig, axes = plt.subplots(n_execs, n_files, squeeze=False)

    row = 0
    col = 0
    for mch_name, mch_execs in zip(mch_names, executions):
        for idx in range(n_execs):
            data = mch_execs[idx]
            title = "%s, exec %d" % (mch_name, idx)
            draw_runseq_subplot(axes[row, col], data, title)
            col += 1
        row += 1
        col = 0

    fig.suptitle(key)
    mng = plt.get_current_fig_manager()
    mng.resize(*mng.window.maxsize())
    plt.show()

if __name__ == "__main__":
    from krun.util import output_name
    try:
        cfile1 = sys.argv[1]
        mch_name1 = sys.argv[2]
        cfile2 = sys.argv[3]
        mch_name2 = sys.argv[4]
    except IndexError:
        usage()

    json_file1 = output_name(cfile1)
    json_file2 = output_name(cfile2)

    with open(json_file1, "r") as fh1:
        data_dct1 = json.load(fh1)
    with open(json_file2, "r") as fh2:
        data_dct2 = json.load(fh2)

    plt.close()  # avoid extra blank window
    main([data_dct1, data_dct2], [mch_name1, mch_name2])
