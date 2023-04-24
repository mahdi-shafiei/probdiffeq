"""There are too many ways to smooth. We assert they all do the same."""

import jax
import jax.numpy as jnp

from probdiffeq import ivpsolve, solution, test_util
from probdiffeq.backend import testing
from probdiffeq.statespace import recipes
from probdiffeq.strategies import smoothers

# todo: both this file and test_checkpoint_same_grid.py call
#  solve_with_python_while_loop(... solver=smo) and solve_and_save_at(solver=fp_smo)
#  this redundancy should be eliminated


@testing.parametrize("k", [1, 3], ids=["1xPts", "3xPts"])  # k * N // 2 off-grid points
@testing.parametrize_with_cases("ode_problem", cases="..problem_cases", has_tag=["nd"])
@testing.parametrize(
    "impl_fn",
    # one for each SSM factorisation
    [
        lambda num_derivatives, **kwargs: recipes.ts0_iso(
            num_derivatives=num_derivatives
        ),
        recipes.ts0_blockdiag,
        recipes.ts0_dense,
    ],
    ids=["IsoTS0", "BlockDiagTS0", "DenseTS0"],
)
def test_smoothing_checkpoint_equals_solver_state(ode_problem, impl_fn, k):
    """In solve_and_save_at(), if the checkpoint-grid equals the solution-grid\
     of a previous call to solve_with_python_while_loop(), \
     the results should be identical."""
    # smo_sol.t is an adaptive grid
    # here, create an even grid which shares one point with the adaptive one.
    # This one point will be used for error-estimation.

    solver_smo = test_util.generate_solver(
        strategy_factory=smoothers.Smoother,
        impl_factory=impl_fn,
        ode_shape=ode_problem.initial_values[0].shape,
        num_derivatives=2,
    )
    solver_fp_smo = test_util.generate_solver(
        strategy_factory=smoothers.FixedPointSmoother,
        impl_factory=impl_fn,
        ode_shape=ode_problem.initial_values[0].shape,
        num_derivatives=2,
    )

    args = (ode_problem.vector_field, ode_problem.initial_values)
    kwargs = {"parameters": ode_problem.args, "atol": 1e-1, "rtol": 1e-1}
    smo_sol = ivpsolve.solve_with_python_while_loop(
        *args, t0=ode_problem.t0, t1=ode_problem.t1, solver=solver_smo, **kwargs
    )
    ts = jnp.linspace(ode_problem.t0, ode_problem.t1, num=k * len(smo_sol.t) // 2)
    u, dense = solution.offgrid_marginals_searchsorted(
        ts=ts[1:-1], solution=smo_sol, solver=solver_smo
    )

    fp_smo_sol = ivpsolve.solve_and_save_at(
        *args, save_at=ts, solver=solver_fp_smo, **kwargs
    )
    fixedpoint_smo_sol = fp_smo_sol[1:-1]  # reference is defined only on the interior

    # Compare all attributes for equality,
    # except for the covariance matrix square roots
    # which are equal modulo orthogonal transformation
    # (they are equal in square, though).
    # The backward models are not expected to be equal.
    assert jnp.allclose(fixedpoint_smo_sol.t, ts[1:-1])
    assert jnp.allclose(fixedpoint_smo_sol.u, u)
    assert jnp.allclose(fixedpoint_smo_sol.marginals.mean, dense.mean)

    # covariances are equal, but cov_sqrtm_lower might not be
    c0 = fixedpoint_smo_sol.marginals.cov_dense()
    c1 = dense.cov_dense()
    assert jnp.allclose(c0, c1)


def _tree_all_allclose(tree1, tree2, **kwargs):
    trees_is_allclose = _tree_allclose(tree1, tree2, **kwargs)
    return jax.tree_util.tree_all(trees_is_allclose)


def _tree_allclose(tree1, tree2, **kwargs):
    def allclose_partial(*args):
        return jnp.allclose(*args, **kwargs)

    return jax.tree_util.tree_map(allclose_partial, tree1, tree2)
