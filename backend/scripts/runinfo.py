"""runinfo.py -- wall time, peak memory and environment, for the artifact.

REPRODUCIBILITY.md promises runtime, memory and environment for the major
analyses (review item M16). Each script that makes one calls `run_info()` at
the end and stores the result under "run_info", so the figure is measured by
the run that produced the numbers rather than remembered.

Peak memory is the process's peak working set, read from the operating system:
GetProcessMemoryInfo on Windows (ctypes, standard library), ru_maxrss
elsewhere. No dependency is added.
"""
from __future__ import annotations

import os
import platform
import sys
import time

_T0 = time.time()


def peak_rss_mb() -> float | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            # the pseudo-handle is -1; without an explicit HANDLE restype ctypes
            # truncates it to a 32-bit int and the call fails silently
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            gpmi = ctypes.windll.psapi.GetProcessMemoryInfo
            gpmi.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            ok = gpmi(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 2 ** 20 if ok else None
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return r / 1024 if sys.platform != "darwin" else r / 2 ** 20
    except Exception:  # noqa: BLE001 -- a missing figure is recorded as None
        return None


def run_info() -> dict:
    import numpy
    try:
        import scipy
        sv = scipy.__version__
    except ImportError:
        sv = None
    return {"wall_s": round(time.time() - _T0, 1),
            "peak_rss_mb": (round(peak_rss_mb()) if peak_rss_mb() else None),
            "python": sys.version.split()[0], "numpy": numpy.__version__,
            "scipy": sv, "platform": platform.platform(),
            "cpu_count": os.cpu_count()}
