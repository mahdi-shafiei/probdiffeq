"""Assert that every recipe yields a decent ODE approximation."""

from probdiffeq import ivpsolve, ivpsolvers, taylor
from probdiffeq.backend import numpy as np
from probdiffeq.backend import ode, testing
from probdiffeq.impl import impl


@testing.case()
def case_ts0():
    try:
        return ivpsolvers.correction_ts0()
    except NotImplementedError:
        return "not_implemented"
    raise RuntimeError


@testing.case()
def case_ts1():
    try:
        return ivpsolvers.correction_ts1()
    except NotImplementedError:
        return "not_implemented"
    raise RuntimeError


@testing.case()
def case_slr0():
    try:
        return ivpsolvers.correction_slr0()
    except NotImplementedError:
        return "not_implemented"
    raise RuntimeError


@testing.case()
def case_slr1():
    try:
        return ivpsolvers.correction_slr1()
    except NotImplementedError:
        return "not_implemented"
    raise RuntimeError


@testing.case()
def case_slr1_gauss_hermite():
    try:
        return ivpsolvers.correction_slr1(
            cubature_fun=ivpsolvers.cubature_gauss_hermite
        )
    except NotImplementedError:
        return "not_implemented"
    raise RuntimeError


@testing.fixture(name="solution")
@testing.parametrize_with_cases("correction_impl", cases=".", prefix="case_")
def fixture_solution(ssm, correction_impl):
    vf, u0, (t0, t1) = ssm.default_ode

    if correction_impl == "not_implemented":
        testing.skip(reason="This type of linearisation has not been implemented.")

    ibm = ivpsolvers.prior_ibm(num_derivatives=2)
    strategy = ivpsolvers.strategy_filter(ibm, correction_impl)
    solver = ivpsolvers.solver_mle(strategy)
    adaptive_solver = ivpsolve.adaptive(solver, atol=1e-2, rtol=1e-2)

    adaptive_kwargs = {"adaptive_solver": adaptive_solver, "dt0": 0.1}

    tcoeffs = taylor.odejet_padded_scan(lambda y: vf(y, t=t0), u0, num=2)
    output_scale = np.ones_like(impl.prototypes.output_scale())
    init = solver.initial_condition(tcoeffs, output_scale)
    return ivpsolve.solve_adaptive_terminal_values(
        vf, init, t0=t0, t1=t1, **adaptive_kwargs
    )


@testing.fixture(name="reference_solution")
def fixture_reference_solution(ssm):
    vf, (u0,), (t0, t1) = ssm.default_ode
    return ode.odeint_dense(vf, (u0,), t0=t0, t1=t1, atol=1e-10, rtol=1e-10)


def test_terminal_value_simulation_matches_reference(solution, reference_solution):
    expected = reference_solution(solution.t)
    received = solution.u

    assert np.allclose(received, expected, rtol=1e-2)
