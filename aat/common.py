from typing import Callable, List

import os
import itertools
import functools
import pandas as pd 


class AATException(Exception):
    pass


def _in_cpp() -> bool:
    pass