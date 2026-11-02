import time
from decimal import Decimal


def ns(seconds): return int(Decimal(str(seconds))*1000000000)


def wait_until(deadline,cancel):
    while not cancel.is_set():
        remaining=deadline-time.monotonic_ns()
        if remaining<=0: return True
        cancel.wait(min(.05,remaining/1e9))
    return False
