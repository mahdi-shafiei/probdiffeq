"""The fixedpoint-smoother and smoother should yield identical results.

That is, when called with correct adaptive- and checkpoint-setups.
"""

from probdiffeq import ivpsolve, ivpsolvers, stats, taylor
from probdiffeq.backend import functools, testing, tree_util
from probdiffeq.backend import numpy as np
from probdiffeq.impl import impl


@testing.fixture(name="solver_setup")
def fixture_solver_setup(ssm):
    vf, (u0,), (t0, t1) = ssm.default_ode

    output_scale = np.ones_like(impl.prototypes.output_scale())

    tcoeffs = taylor.odejet_padded_scan(lambda y: vf(y, t=t0), (u0,), num=2)
    return {
        "vf": vf,
        "tcoeffs": tcoeffs,
        "t0": t0,
        "t1": t1,
        "output_scale": output_scale,
    }


@testing.fixture(name="solution_smoother")
def fixture_solution_smoother(solver_setup):
    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    ts0 = ivpsolvers.correction_ts0()
    strategy = ivpsolvers.strategy_smoother(ibm, ts0)
    solver = ivpsolvers.solver(strategy)
    adaptive_solver = ivpsolve.adaptive(solver, atol=1e-3, rtol=1e-3)

    tcoeffs, output_scale = solver_setup["tcoeffs"], solver_setup["output_scale"]
    init = solver.initial_condition(tcoeffs, output_scale)
    return ivpsolve.solve_adaptive_save_every_step(
        solver_setup["vf"],
        init,
        t0=solver_setup["t0"],
        t1=solver_setup["t1"],
        dt0=0.1,
        adaptive_solver=adaptive_solver,
    )


def test_fixedpoint_smoother_equivalent_same_grid(solver_setup, solution_smoother):
    """Test that with save_at=smoother_solution.t, the results should be identical."""
    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    ts0 = ivpsolvers.correction_ts0()
    strategy = ivpsolvers.strategy_fixedpoint(ibm, ts0)
    solver = ivpsolvers.solver(strategy)
    adaptive_solver = ivpsolve.adaptive(solver, atol=1e-3, rtol=1e-3)

    save_at = solution_smoother.t

    tcoeffs, output_scale = solver_setup["tcoeffs"], solver_setup["output_scale"]
    init = solver.initial_condition(tcoeffs, output_scale)

    solution_fixedpoint = ivpsolve.solve_adaptive_save_at(
        solver_setup["vf"],
        init,
        save_at=save_at,
        adaptive_solver=adaptive_solver,
        dt0=0.1,
    )
    assert testing.tree_all_allclose(solution_fixedpoint, solution_smoother)


def test_fixedpoint_smoother_equivalent_different_grid(solver_setup, solution_smoother):
    """Test that the interpolated smoother result equals the save_at result."""
    save_at = solution_smoother.t

    # Re-generate the smoothing solver
    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    ts0 = ivpsolvers.correction_ts0()
    strategy = ivpsolvers.strategy_smoother(ibm, ts0)
    solver_smoother = ivpsolvers.solver(strategy)

    # Compute the offgrid-marginals
    ts = np.linspace(save_at[0], save_at[-1], num=7, endpoint=True)
    u_interp, marginals_interp = stats.offgrid_marginals_searchsorted(
        ts=ts[1:-1], solution=solution_smoother, solver=solver_smoother
    )

    # Generate a fixedpoint solver and solve (saving at the interpolation points)
    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    ts0 = ivpsolvers.correction_ts0()
    strategy = ivpsolvers.strategy_fixedpoint(ibm, ts0)
    solver = ivpsolvers.solver(strategy)
    adaptive_solver = ivpsolve.adaptive(solver, atol=1e-3, rtol=1e-3)
    tcoeffs, output_scale = solver_setup["tcoeffs"], solver_setup["output_scale"]
    init = solver.initial_condition(tcoeffs, output_scale)

    solution_fixedpoint = ivpsolve.solve_adaptive_save_at(
        solver_setup["vf"], init, save_at=ts, adaptive_solver=adaptive_solver, dt0=0.1
    )

    # Extract the interior points of the save_at solution
    # (because only there is the interpolated solution defined)
    u_fixedpoint = solution_fixedpoint.u[1:-1]
    marginals_fixedpoint = tree_util.tree_map(
        lambda s: s[1:-1], solution_fixedpoint.marginals
    )

    # Compare QOI and marginals
    marginals_allclose_func = functools.vmap(testing.marginals_allclose)
    assert testing.tree_all_allclose(u_fixedpoint, u_interp)
    assert np.all(marginals_allclose_func(marginals_fixedpoint, marginals_interp))
