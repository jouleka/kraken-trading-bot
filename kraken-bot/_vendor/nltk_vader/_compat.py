# Natural Language Toolkit: pairwise
# Copyright (C) 2001-2026 NLTK Project
# Licensed under Apache 2.0; see LICENSE.txt.
# Local extraction: the original pairwise function, without the other nltk.util imports.

from itertools import tee


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)
