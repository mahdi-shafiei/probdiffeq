"""Compare solve_fixed_grid to solve_adaptive_save_every_step."""

from probdiffeq import ivpsolve, ivpsolvers, taylor
from probdiffeq.backend import numpy as np
from probdiffeq.backend import testing
from probdiffeq.impl import impl


def test_fixed_grid_result_matches_adaptive_grid_result(ssm):
    vf, u0, (t0, t1) = ssm.default_ode

    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    ts0 = ivpsolvers.correction_ts0()
    strategy = ivpsolvers.strategy_filter(ibm, ts0)
    solver = ivpsolvers.solver_mle(strategy)
    control = ivpsolve.control_integral_clipped()  # Any clipped controller will do.
    adaptive_solver = ivpsolve.adaptive(solver, atol=1e-2, rtol=1e-2, control=control)

    tcoeffs = taylor.odejet_padded_scan(lambda y: vf(y, t=t0), u0, num=2)
    output_scale = np.ones_like(impl.prototypes.output_scale())
    init = solver.initial_condition(tcoeffs, output_scale=output_scale)
    args = (vf, init)

    adaptive_kwargs = {
        "t0": t0,
        "t1": t1,
        "dt0": 0.1,
        "adaptive_solver": adaptive_solver,
    }
    solution_adaptive = ivpsolve.solve_adaptive_save_every_step(
        *args, **adaptive_kwargs
    )

    grid_adaptive = solution_adaptive.t
    fixed_kwargs = {"grid": grid_adaptive, "solver": solver}
    solution_fixed = ivpsolve.solve_fixed_grid(*args, **fixed_kwargs)
    assert testing.tree_all_allclose(solution_adaptive, solution_fixed)
