"""There are too many ways to smooth. We assert they all do the same."""

import jax.numpy as jnp
from pytest_cases import case, parametrize, parametrize_with_cases

from odefilter import ivpsolve, recipes


@case
@parametrize("n", [2])
def smoother_fixedpoint_smoother_pair_fixedpoint_eks0(n):
    eks0 = recipes.eks0_isotropic_dynamic(num_derivatives=n)
    fixedpoint_eks0 = recipes.eks0_isotropic_dynamic_fixedpoint(num_derivatives=n)
    return eks0, fixedpoint_eks0


@case
@parametrize("n", [2])
def smoother_fixedpoint_smoother_pair_two_eks0(n, tol):
    # if the checkpoints are equal to the solver states,
    # then the checkpoint-simulator replicates _exactly_ what the non-checkpoint-
    # smoother does. So the tests must also pass in this setup.
    eks0a = recipes.eks0_isotropic_dynamic(num_derivatives=n)
    eks0b = recipes.eks0_isotropic_dynamic(num_derivatives=n)
    return eks0a, eks0b


@parametrize_with_cases("vf, u0, t0, t1, p", cases="..ivp_cases", prefix="problem_")
@parametrize_with_cases(
    "eks, fixedpoint_eks", cases=".", prefix="smoother_fixedpoint_smoother_pair_"
)
@parametrize("tol", [1e-2])
def test_smoothing_checkpoint_equals_solver_state(
    vf, u0, t0, t1, p, eks, fixedpoint_eks, tol
):
    """In simulate_checkpoints(), if the checkpoint-grid equals the solution-grid\
     of a previous call to solve(), the results should be identical."""
    eks_sol = ivpsolve.solve(
        vf,
        u0,
        t0=t0,
        t1=t1,
        parameters=p,
        solver=eks[0],
        info_op=eks[1],
        atol=1e-2 * tol,
        rtol=tol,
    )

    fixedpoint_eks_sol = ivpsolve.simulate_checkpoints(
        vf,
        u0,
        ts=eks_sol.t,
        parameters=p,
        solver=fixedpoint_eks[0],
        info_op=fixedpoint_eks[1],
        atol=1e-2 * tol,
        rtol=tol,
    )

    tols = {"atol": 1e-2, "rtol": 1e-2}
    assert jnp.allclose(fixedpoint_eks_sol.t, eks_sol.t, **tols)
    assert jnp.allclose(fixedpoint_eks_sol.u, eks_sol.u, **tols)
    assert jnp.allclose(
        fixedpoint_eks_sol.marginals.mean, eks_sol.marginals.mean, **tols
    )
    assert jnp.allclose(
        fixedpoint_eks_sol.posterior.backward_model.noise.mean,
        eks_sol.posterior.backward_model.noise.mean,
        **tols
    )
    assert jnp.allclose(
        fixedpoint_eks_sol.output_scale_sqrtm, eks_sol.output_scale_sqrtm, **tols
    )

    # covariances are equal, but cov_sqrtm_lower might not be

    def cov(x):
        return jnp.einsum("...jk,...lk->...jl", x, x)

    l0 = fixedpoint_eks_sol.marginals.cov_sqrtm_lower
    l1 = eks_sol.marginals.cov_sqrtm_lower
    assert jnp.allclose(cov(l0), cov(l1), **tols)

    l0 = fixedpoint_eks_sol.posterior.backward_model.noise.cov_sqrtm_lower
    l1 = eks_sol.posterior.backward_model.noise.cov_sqrtm_lower
    assert jnp.allclose(cov(l0), cov(l1), **tols)