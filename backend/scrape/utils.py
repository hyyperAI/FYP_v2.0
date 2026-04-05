"""
backend/scrape/utils.py

Utility functions for the scraping module.
"""

import platform
import ctypes
import time
import random
from datetime import datetime


def split_list_into_chunks(lst: list, num_chunks: int) -> list[list]:
    """
    Split a list into `num_chunks` chunks.

    .. note:: The elements in each chunk aren't in the same order as the original list.

    Parameters
    ----------
    lst: list
        The list to split.
    num_chunks: int
        The number of chunks to split. If 1, a list containing `lst` is returned, if larger or equal to the length
        of `lst`, a list containing `len(lst)` chunks (lists) each containing one element is returned.

    Returns
    -------
    chunks: list[list]
        A list of lists (chunks).
    """
    chunks = []
    for i in range(num_chunks):
        # Create a new chunk with elements at positions i, i + num_chunks, i + 2*num_chunks, etc.
        chunk = lst[i::num_chunks]
        if chunk:
            chunks.append(chunk)
    return chunks


def inhibit_sleep(inhibit: bool = False) -> None:
    """
    Prevents a Windows computer from going to sleep while the current thread is running.
    .. note:: This function needs to be called periodically in case of inhibiting sleep.
    """
    # For more information about how this works what are the values user, see:
    # https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate
    es_continues = 0x80000000
    es_system_required = 0x00000001
    if platform.system() == "Windows":
        if inhibit:
            ctypes.windll.kernel32.SetThreadExecutionState(es_continues | es_system_required)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(es_continues)


def time_print(message: str) -> None:
    """Print a message alongside the current time."""
    print(f"{datetime.now().isoformat(sep=' ', timespec='seconds')}: {message}")


def sleep(a: float = 0.5, b: float = 1) -> None:
    """Sleeps for a random amount between `a` and `b` seconds."""
    time.sleep(random.uniform(a, b))


__all__ = [
    'split_list_into_chunks',
    'inhibit_sleep',
    'time_print',
    'sleep',
]
