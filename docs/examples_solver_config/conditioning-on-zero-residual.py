# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Probabilistic solvers as collocation methods
#
# Probabilistic solvers condition a prior distribution
# on satisfying a zero-ODE-residual on a specified grid.
#

# +
"""Demonstrate how probabilistic solvers work via conditioning on constraints."""

import jax
import jax.numpy as jnp
import matplotlib.pyplot as plt
from diffeqzoo import backend

from probdiffeq import ivpsolve, ivpsolvers, stats, taylor
from probdiffeq.impl import impl
from probdiffeq.util.doc_util import notebook

# -

plt.rcParams.update(notebook.plot_style())
plt.rcParams.update(notebook.plot_sizes())

# +
if not backend.has_been_selected:
    backend.select("jax")  # ivp examples in jax

jax.config.update("jax_platform_name", "cpu")
jax.config.update("jax_enable_x64", True)

# Make a solver
impl.select("dense", ode_shape=(1,))

# +
# Create an ODE problem


@jax.jit
def vector_field(y, t):  # noqa: ARG001
    """Evaluate the logistic ODE vector field."""
    return 10.0 * y * (2.0 - y)


t0, t1 = 0.0, 0.5
u0 = jnp.asarray([0.1])

# +
# Assemble the discretised prior (with and without the correct Taylor coefficients)

NUM_DERIVATIVES = 2
ts = jnp.linspace(t0, t1, num=500, endpoint=True)
init_raw, transitions = ivpsolvers.prior_ibm_discrete(
    ts, num_derivatives=NUM_DERIVATIVES, output_scale=100.0
)

markov_seq_prior = stats.MarkovSeq(init_raw, transitions)


tcoeffs = taylor.odejet_padded_scan(
    lambda y: vector_field(y, t=t0), (u0,), num=NUM_DERIVATIVES
)
init_tcoeffs = impl.normal.from_tcoeffs(tcoeffs, num_derivatives=NUM_DERIVATIVES)
markov_seq_tcoeffs = stats.MarkovSeq(init_tcoeffs, transitions)

# +
# Compute the posterior

slr1 = ivpsolvers.correction_ts1()
ibm = ivpsolvers.prior_ibm(num_derivatives=NUM_DERIVATIVES)
solver = ivpsolvers.solver(ivpsolvers.strategy_fixedpoint(ibm, slr1))
adaptive_solver = ivpsolve.adaptive(solver, atol=1e-1, rtol=1e-2)

dt0 = ivpsolve.dt0(lambda y: vector_field(y, t=t0), (u0,))

init = solver.initial_condition(tcoeffs, output_scale=1.0)
sol = ivpsolve.solve_adaptive_save_at(
    vector_field, init, save_at=ts, dt0=1.0, adaptive_solver=adaptive_solver
)
# posterior = stats.calibrate(sol.posterior, sol.output_scale)
markov_seq_posterior = stats.markov_select_terminal(sol.posterior)

# +
# Compute marginals

margs_prior = stats.markov_marginals(markov_seq_prior, reverse=False)
margs_tcoeffs = stats.markov_marginals(markov_seq_tcoeffs, reverse=False)
margs_posterior = stats.markov_marginals(markov_seq_posterior, reverse=True)

# +
# Compute samples

num_samples = 5
key = jax.random.PRNGKey(seed=1)
(_qoi, samples_prior), _ = stats.markov_sample(
    key, markov_seq_prior, shape=(num_samples,), reverse=False
)
(_qoi, samples_tcoeffs), _ = stats.markov_sample(
    key, markov_seq_tcoeffs, shape=(num_samples,), reverse=False
)
(_qoi, samples_posterior), _ = stats.markov_sample(
    key, markov_seq_posterior, shape=(num_samples,), reverse=True
)

# +
# Plot the results

fig, (axes_state, axes_residual, axes_log_abs) = plt.subplots(
    nrows=3, ncols=3, sharex=True, sharey="row", constrained_layout=True, figsize=(8, 5)
)
axes_state[0].set_title("Prior")
axes_state[1].set_title("w/ Initial condition")
axes_state[2].set_title("Posterior")

sample_style = {"marker": "None", "alpha": 0.99, "linewidth": 0.75}
mean_style = {
    "marker": "None",
    "color": "black",
    "linestyle": "dashed",
    "linewidth": 0.99,
}


def log_residual(*args):
    """Evaluate the log-ODE-residual."""
    return jnp.log10(jnp.abs(residual(*args)))


def residual(x, t):
    """Evaluate the ODE residual."""
    return x[..., 1] - jax.vmap(vector_field)(x[..., 0], t)


for i in range(num_samples):
    # Plot all state-samples
    axes_state[0].plot(ts[1:], samples_prior[i, ..., 0], **sample_style, color="C0")
    axes_state[1].plot(ts[1:], samples_tcoeffs[i, ..., 0], **sample_style, color="C1")
    axes_state[2].plot(
        ts[:-1], samples_posterior[i, ..., 0], **sample_style, color="C2"
    )

    # Plot all residual-samples
    axes_residual[0].plot(
        ts[:-1], residual(samples_prior[i, ...], ts[:-1]), **sample_style, color="C0"
    )
    axes_residual[1].plot(
        ts[:-1], residual(samples_tcoeffs[i, ...], ts[:-1]), **sample_style, color="C1"
    )
    axes_residual[2].plot(
        ts[:-1],
        residual(samples_posterior[i, ...], ts[:-1]),
        **sample_style,
        color="C2",
    )

    # Plot all log-residual samples
    axes_log_abs[0].plot(
        ts[:-1],
        log_residual(samples_prior[i, ...], ts[:-1]),
        **sample_style,
        color="C0",
    )
    axes_log_abs[1].plot(
        ts[:-1],
        log_residual(samples_tcoeffs[i, ...], ts[:-1]),
        **sample_style,
        color="C1",
    )
    axes_log_abs[2].plot(
        ts[:-1],
        log_residual(samples_posterior[i, ...], ts[:-1]),
        **sample_style,
        color="C2",
    )

# Plot state means
axes_state[0].plot(ts[1:], margs_prior.mean[..., 0], **mean_style)
axes_state[1].plot(ts[1:], margs_tcoeffs.mean[..., 0], **mean_style)
axes_state[2].plot(ts[:-1], margs_posterior.mean[..., 0], **mean_style)

# Plot residual means
axes_residual[0].plot(ts[:-1], residual(margs_prior.mean, ts[:-1]), **mean_style)
axes_residual[1].plot(ts[:-1], residual(margs_tcoeffs.mean, ts[:-1]), **mean_style)
axes_residual[2].plot(ts[:-1], residual(margs_posterior.mean, ts[:-1]), **mean_style)

# Plot residual log-magnitudes
axes_log_abs[0].plot(ts[:-1], log_residual(margs_prior.mean, ts[:-1]), **mean_style)
axes_log_abs[1].plot(ts[:-1], log_residual(margs_tcoeffs.mean, ts[:-1]), **mean_style)
axes_log_abs[2].plot(ts[:-1], log_residual(margs_posterior.mean, ts[:-1]), **mean_style)

# Set the x- and y-ticks/limits
axes_state[0].set_xticks((t0, (t0 + t1) / 2, t1))
axes_state[0].set_xlim((t0, t1))

axes_state[0].set_ylim((-1, 3))
axes_state[0].set_yticks((-1, 1, 3))

axes_residual[0].set_ylim((-10.0, 20))
axes_residual[0].set_yticks((-10.0, 5, 20))

axes_log_abs[0].set_ylim((-6, 4))
axes_log_abs[0].set_yticks((-6, -1, 4))

# Label the x- and y-axes
axes_state[0].set_ylabel("Solution")
axes_residual[0].set_ylabel("Residual")
axes_log_abs[0].set_ylabel(r"Log-residual")
axes_log_abs[0].set_xlabel("Time $t$")
axes_log_abs[1].set_xlabel("Time $t$")
axes_log_abs[2].set_xlabel("Time $t$")

# Show the result
fig.align_ylabels()
plt.show()
