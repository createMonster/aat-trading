from typing import List, Any
import bisect

def _insort(a: List, x: Any) -> bool:
    """Insert x into a if it's not currently there"""
    i = bisect.bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return False
    
    a.insert(i, x)
    return True