# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""DRAG pulse calibration experiment."""

from typing import List, Union

import numpy as np

import qiskit_experiments.curve_analysis as curve
from qiskit_experiments.curve_analysis.fit_function import cos


class DragCalAnalysis(curve.CurveAnalysis):
    r"""Drag calibration analysis based on a fit to a cosine function.

    # section: fit_model

        Analyse a Drag calibration experiment by fitting three series each to a cosine
        function. The three functions share the phase parameter (i.e. beta), amplitude, and
        baseline. The frequencies of the oscillations are related through the number of
        repetitions of the Drag gates. Several initial guesses are tried if the user
        does not provide one. The fit function is

        .. math::

            y_i = {\rm amp} \cos\left(2 \pi\cdot {\rm reps}_i \cdot {\rm freq}\cdot x -
            2 \pi\cdot {\rm reps}_i \cdot {\rm freq}\cdot \beta\right) + {\rm base}

        Here, the fit parameter :math:`freq` is the frequency of the oscillation of a
        single pair of Drag plus and minus rotations and :math:`{\rm reps}_i` is the number
        of times that the Drag plus and minus rotations are repeated in curve :math:`i`.
        Note that the aim of the Drag calibration is to find the :math:`\beta` that
        minimizes the phase shifts. This implies that the optimal :math:`\beta` occurs when
        all three :math:`y` curves are minimum, i.e. they produce the ground state. This
        occurs when

        .. math::

            {\rm reps}_i * {\rm freq} * (x - \beta) = N

        is satisfied with :math:`N` an integer. Note, however, that this condition
        produces a minimum only when the amplitude is negative. To ensure this is
        the case, we bound the amplitude to be less than 0.

    # section: fit_parameters
        defpar \rm amp:
            desc: Amplitude of all series.
            init_guess: The maximum y value scaled by -1, -0.5, and -0.25.
            bounds: [-2, 0] scaled to the maximum signal value.

        defpar \rm base:
            desc: Base line of all series.
            init_guess: Half the maximum y-value of the data.
            bounds: [-1, 1] scaled to the maximum y-value.

        defpar {\rm freq}:
            desc: Frequency of oscillation as a function of :math:`\beta` for a single pair
                of DRAG plus and minus pulses.
            init_guess: For the curve with the most Drag pulse repetitions, the peak frequency
                of the power spectral density is found and then divided by the number of repetitions.
            bounds: [0, inf].

        defpar \beta:
            desc: Common beta offset. This is the parameter of interest.
            init_guess: Linearly spaced between the maximum and minimum scanned beta.
            bounds: [-min scan range, max scan range].
    """

    __series__ = [
        curve.SeriesDef(
            fit_func=lambda x, amp, freq, reps0, reps1, reps2, beta, base: cos(
                x, amp=amp, freq=reps0 * freq, phase=-2 * np.pi * reps0 * freq * beta, baseline=base
            ),
            plot_color="blue",
            name="series-0",
            filter_kwargs={"series": 0},
            plot_symbol="o",
            model_description=r"{\rm amp} \cos\left(2 \pi\cdot {\rm reps}_0\cdot {\rm freq} [x "
            r"- \beta]\right) + {\rm base}",
        ),
        curve.SeriesDef(
            fit_func=lambda x, amp, freq, reps0, reps1, reps2, beta, base: cos(
                x, amp=amp, freq=reps1 * freq, phase=-2 * np.pi * reps1 * freq * beta, baseline=base
            ),
            plot_color="green",
            name="series-1",
            filter_kwargs={"series": 1},
            plot_symbol="^",
            model_description=r"{\rm amp} \cos\left(2 \pi\cdot {\rm reps}_1\cdot {\rm freq} [x "
            r"- \beta]\right) + {\rm base}",
        ),
        curve.SeriesDef(
            fit_func=lambda x, amp, freq, reps0, reps1, reps2, beta, base: cos(
                x, amp=amp, freq=reps2 * freq, phase=-2 * np.pi * reps2 * freq * beta, baseline=base
            ),
            plot_color="red",
            name="series-2",
            filter_kwargs={"series": 2},
            plot_symbol="v",
            model_description=r"{\rm amp} \cos\left(2 \pi\cdot {\rm reps}_2\cdot {\rm freq} [x "
            r"- \beta]\right) + {\rm base}",
        ),
    ]

    @classmethod
    def _default_options(cls):
        """Return the default analysis options.

        See :meth:`~qiskit_experiment.curve_analysis.CurveAnalysis._default_options` for
        descriptions of analysis options.
        """
        default_options = super()._default_options()
        default_options.curve_plotter.set_options(
            xlabel="Beta",
            ylabel="Signal (arb. units)",
        )
        default_options.result_parameters = ["beta"]
        default_options.fixed_parameters = {"reps0": 1, "reps1": 3, "reps2": 5}
        default_options.normalization = True

        return default_options

    def _generate_fit_guesses(
        self, user_opt: curve.FitOptions
    ) -> Union[curve.FitOptions, List[curve.FitOptions]]:
        """Compute the initial guesses.

        Args:
            user_opt: Fit options filled with user provided guess and bounds.

        Returns:
            List of fit options that are passed to the fitter function.
        """
        # Use a fast Fourier transform to guess the frequency.
        x_data = self._data("series-0").x
        min_beta, max_beta = min(x_data), max(x_data)

        # Use the highest-frequency curve to estimate the oscillation frequency.
        series_label, reps_label = max(
            ("series-0", "reps0"),
            ("series-1", "reps1"),
            ("series-2", "reps2"),
            key=lambda x: self.options.fixed_parameters[x[1]],
        )
        curve_data = self._data(series_label)
        reps2 = self.options.fixed_parameters[reps_label]
        freqs_guess = curve.guess.frequency(curve_data.x, curve_data.y) / reps2
        user_opt.p0.set_if_empty(freq=freqs_guess)

        avg_x = (max(x_data) + min(x_data)) / 2
        span_x = max(x_data) - min(x_data)
        beta_bound = max(5 / user_opt.p0["freq"], span_x)

        ptp_y = np.ptp(self._data().y)
        user_opt.bounds.set_if_empty(
            amp=(-2 * ptp_y, 0),
            freq=(0, np.inf),
            beta=(avg_x - beta_bound, avg_x + beta_bound),
            base=(min(self._data().y) - ptp_y, max(self._data().y) + ptp_y),
        )
        base_guess = (max(self._data().y) - min(self._data().y)) / 2
        user_opt.p0.set_if_empty(base=(user_opt.p0["amp"] or base_guess))

        # Drag curves can sometimes be very flat, i.e. averages of y-data
        # and min-max do not always make good initial guesses. We therefore add
        # 0.5 to the initial guesses. Note that we also set amp=-0.5 because the cosine function
        # becomes +1 at zero phase, i.e. optimal beta, in which y data should become zero
        # in discriminated measurement level.
        options = []
        for amp_factor in (-1, -0.5, -0.25):
            for beta_guess in np.linspace(min_beta, max_beta, 20):
                new_opt = user_opt.copy()
                new_opt.p0.set_if_empty(amp=ptp_y * amp_factor, beta=beta_guess)
                options.append(new_opt)

        return options

    def _post_process_fit_result(self, fit_result: curve.FitData) -> curve.FitData:
        r"""Post-process the fit result from a Drag analysis.

        The Drag analysis should return the beta value that is closest to zero.
        Since the oscillating term is of the form

        .. math::

            \cos(2 \pi\cdot {\rm reps}_i \cdot {\rm freq}\cdot [x - \beta])

        There is a periodicity in beta. This post processing finds the beta that is
        closest to zero by performing the minimization using the modulo function.

        .. math::

            n_\text{min} = \min_{n}|\beta_\text{fit} + n / {\rm freq}|

        and assigning the new beta value to

        .. math::

            \beta = \beta_\text{fit} + n_\text{min} / {\rm freq}.
        """
        beta = fit_result.popt[2]
        freq = fit_result.popt[1]
        fit_result.popt[2] = ((beta + 1 / freq / 2) % (1 / freq)) - 1 / freq / 2
        return fit_result

    def _evaluate_quality(self, fit_data: curve.FitData) -> Union[str, None]:
        """Algorithmic criteria for whether the fit is good or bad.

        A good fit has:
            - a reduced chi-squared lower than three,
            - a DRAG parameter value within the first period of the lowest number of repetitions,
            - an error on the drag beta smaller than the beta.
        """
        fit_beta = fit_data.fitval("beta")
        fit_freq = fit_data.fitval("freq")

        criteria = [
            fit_data.reduced_chisq < 3,
            abs(fit_beta.nominal_value) < 1 / fit_freq.nominal_value / 2,
            curve.is_error_not_significant(fit_beta),
        ]

        if all(criteria):
            return "good"

        return "bad"
