// Note:
// On Linux nanotime() calls clock_gettime() with the CLOCK_MONOTONIC flag.
// https://bugs.openjdk.java.net/browse/JDK-8006942
// This is not quite ideal. We should use CLOCK_MONOTONIC_RAW instead.
// For this reason we use JNI to make a call to clock_gettime() ourselves.

// All entry points must implement this

class startup_runner {
    static {
        System.loadLibrary("kruntime");
    }

    public static void main(String args[]) {
        IterationsRunner.JNI_krun_measure(1);
        double startTime = IterationsRunner.JNI_krun_get_wallclock(1);
        System.out.print(startTime);
        System.out.println("], [-1.0, -1.0]]");
    }
}
