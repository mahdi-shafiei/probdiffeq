"""Tests for square-root matrices.

These are so crucial and annoying to debug that they need their own test set.
"""

from math import prod

from probdiffeq.backend import functools, linalg, testing, tree_util
from probdiffeq.backend import numpy as np
from probdiffeq.util import cholesky_util

_SHAPES = ([(4, 3), (3, 3), (4, 4)], [(2, 3), (3, 3), (2, 2)])


@testing.parametrize("HCshape, Cshape, Xshape", _SHAPES)
def test_revert_conditional(HCshape, Cshape, Xshape):
    HC = _some_array(HCshape) + 1.0
    C = _some_array(Cshape) + 2.0
    X = _some_array(Xshape) + 3.0 + np.eye(Xshape[0])

    S = HC @ HC.T + X @ X.T
    K = C @ HC.T @ linalg.inv(S)
    C1 = C @ C.T - K @ S @ K.T

    extra, (bw_noise, g) = cholesky_util.revert_conditional(
        R_X_F=HC.T, R_X=C.T, R_YX=X.T
    )

    def cov(x):
        return x.T @ x

    assert np.allclose(cov(extra), S)
    assert np.allclose(g, K)
    assert np.allclose(cov(bw_noise), C1)


@testing.parametrize("Cshape, HCshape", ([(3, 3), (2, 3)],))
def test_revert_kernel_noisefree(Cshape, HCshape):
    C = _some_array(Cshape) + 1.0
    HC = _some_array(HCshape) + 2.0

    S = HC @ HC.T
    K = C @ HC.T @ linalg.inv(S)
    C1 = C @ C.T - K @ S @ K.T

    extra, (bw_noise, g) = cholesky_util.revert_conditional_noisefree(
        R_X_F=HC.T, R_X=C.T
    )

    def cov(x):
        return x.T @ x

    assert np.allclose(cov(extra), S)
    assert np.allclose(g, K)
    assert np.allclose(cov(bw_noise), C1)


def _some_array(shape):
    return np.arange(1.0, 1.0 + prod(shape)).reshape(shape)


def test_sqrt_sum_square_scalar():
    a = 3.0
    b = 4.0
    c = 5.0
    expected = np.sqrt(a**2 + b**2 + c**2)
    received = cholesky_util.sqrt_sum_square_scalar(a, b, c)
    assert np.allclose(expected, received)


def test_sqrt_sum_square_error():
    a = 3.0 * np.eye(2)
    b = 4.0 * np.eye(2)
    c = 5.0 * np.eye(2)
    with testing.raises(ValueError, match="scalar"):
        _ = cholesky_util.sqrt_sum_square_scalar(a, b, c)


def test_reverse_conditional_jacrev_zero_matrix():
    """For zero-valued input covariances, reverse-mode gradients need a trick.

    This resolves issue 668.
    """
    C = _some_array((3, 3)) * 0.0
    HC = _some_array((2, 3)) * 0.0
    X = _some_array((2, 2)) + 3.0 + np.eye(2)

    result = functools.jacrev(cholesky_util.revert_conditional)(HC.T, C.T, X.T)
    is_not_nan = _tree_is_free_of_nans(result)
    assert is_not_nan


def test_sum_of_sqrtm_factors_jacrev_zero_matrix():
    """For zero-valued input covariances, reverse-mode gradients need a trick.

    This resolves issue 668.
    """
    C = _some_array((3, 3)) * 0.0
    HC = _some_array((3, 2))

    result = functools.jacrev(cholesky_util.sum_of_sqrtm_factors)((C.T, HC.T))
    is_not_nan = _tree_is_free_of_nans(result)
    assert is_not_nan


def _tree_is_free_of_nans(tree):
    def contains_no_nan(x):
        return np.logical_not(np.any(np.isnan(x)))

    tree_contains_no_nan = tree_util.tree_map(contains_no_nan, tree)
    return tree_util.tree_all(tree_contains_no_nan)
