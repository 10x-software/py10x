#pragma once
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>
#include <bcurve.h>
#include "bcompounding.h"

//==
//   Brent's method root finder  (Brent-Dekker)
//   Requires f(a)*f(b) < 0.  Converges to xtol absolute tolerance.
//==
template<typename F>
double brent_solve(F&& f, double a, double b, double xtol, int max_iter = 200) {
    double fa = f(a), fb = f(b);
    if (fa == 0.0) return a;
    if (fb == 0.0) return b;
    if ((fa > 0.0) == (fb > 0.0))
        throw std::runtime_error("brent_solve: f(a) and f(b) must have opposite signs");

    double c = a, fc = fa, d = b - a, e = d;
    for (int i = 0; i < max_iter; ++i) {
        if ((fb > 0.0) == (fc > 0.0)) { c = a; fc = fa; d = e = b - a; }
        if (std::abs(fc) < std::abs(fb)) {
            a = b; b = c; c = a;
            fa = fb; fb = fc; fc = fa;
        }
        double tol = 2.0 * std::numeric_limits<double>::epsilon() * std::abs(b) + 0.5 * xtol;
        double m   = 0.5 * (c - b);
        if (std::abs(m) <= tol || fb == 0.0) return b;
        if (std::abs(e) >= tol && std::abs(fa) > std::abs(fb)) {
            double s = fb / fa, p, q;
            if (a == c) {
                p = 2.0 * m * s;
                q = 1.0 - s;
            } else {
                double r = fb / fc;
                double t = fa / fc;
                p = s * (2.0 * m * t * (t - r) - (b - a) * (r - 1.0));
                q = (t - 1.0) * (r - 1.0) * (s - 1.0);
            }
            if (p > 0.0) q = -q; else p = -p;
            if (2.0 * p < std::min(3.0 * m * q - std::abs(tol * q), std::abs(e * q)))
                { e = d; d = p / q; }
            else
                { e = m; d = m; }
        } else {
            e = m; d = m;
        }
        a = b; fa = fb;
        b += (std::abs(d) > tol) ? d : (m > 0.0 ? tol : -tol);
        fb = f(b);
    }
    return b;
}

//==
//   BDateCurve helpers
//   BDateCurve::update(py::object, double) and ::value(py::object) hide the
//   CurveTemplate<int> overloads, so qualified calls are needed in C++.
//==
inline void bcurve_update(BDateCurve& curve, int ord, double v) {
    curve.CurveTemplate<int>::update(ord, v);
}
inline double bcurve_value(const BDateCurve& curve, int ord) {
    return curve.CurveTemplate<int>::value(ord);
}

//==
//   bootstrap_cash_deposit
//
//   Solves:  rate_fwd(start, end; curve[end_ord]=x) == quote
//
//   No curve I/O inside the hot loop — only compounding_apply math.
//   Caller precomputes:
//     acc_start  = compounding_apply(comp, R2A, dc_int(today,start), curve[start_ord])
//                  or 1.0 if start == today
//     t_today_end  = dc_int(today, end)      (internal dc convention)
//     t_start_end  = dc_quot(start, end)     (quoting dc convention)
//
//   If `start` falls beyond the last already-fixed curve knot (i.e. its value would
//   only be known once `end` itself is bootstrapped), the caller instead sets
//   gap_frac >= 0: the curve's own LINEAR interior interpolation makes curve[start]
//   a function of x = curve[end] (interpolated between the last fixed knot and the
//   point being solved), so acc_start must be recomputed each iteration —
//     r_start(x) = r_fixed + gap_frac * (x - r_fixed)
//   gap_frac < 0 means start is fully determined by already-fixed knots, and
//   acc_start is the true precomputed constant.
//==
inline void bootstrap_cash_deposit(
    BDateCurve& curve,
    int    bot_ord,
    int    end_ord,
    double acc_start,
    double t_today_end,
    double t_start_end,
    int    comp,        // zrc.compounding.value  (internal)
    int    quot_comp,   // zrc.quoting_compounding.value
    double quote,
    double lo, double hi, double xtol,
    double t_today_start = 0.0,
    double gap_frac      = -1.0,
    double r_fixed       = 0.0
) {
    auto f = [&](double x) -> double {
        double acc_s;
        if (gap_frac >= 0.0) {
            double r_start = r_fixed + gap_frac * (x - r_fixed);
            acc_s = compounding_apply(comp, BCompoundTransform::RATE_TO_ACCRUAL, t_today_start, r_start);
        } else {
            acc_s = acc_start;
        }
        double acc_end = compounding_apply(comp,      BCompoundTransform::RATE_TO_ACCRUAL, t_today_end, x);
        double acc_fwd = acc_end / acc_s;
        double rate    = compounding_apply(quot_comp, BCompoundTransform::ACCRUAL_TO_RATE, t_start_end, acc_fwd);
        return rate - quote;
    };
    double root = brent_solve(f, lo, hi, xtol);
    bcurve_update(curve, end_ord, root);
    if (curve.size() < 3)
        bcurve_update(curve, bot_ord, root);
}

//==
//   bootstrap_swap
//
//   Solves:  swap_rate_simple(curve[last_pay_ord]=x) == quote
//
//   No curve I/O inside the hot loop.
//   Caller precomputes:
//     t_today_last  = dc_int(today, last_pay)
//     annuity_const = sum(dc_frac[i] * df(pay_i, today)) for periods whose pay date
//                     is already determined by fixed (already-bootstrapped) knots
//     last_dc_frac  = fixed-leg dc frac for last period
//     df_spot       = discount_factor(spot_date, today)
//
//   Any intermediate period whose pay date falls beyond the last fixed knot (and
//   before last_pay) has a discount factor that depends on x through the curve's
//   own LINEAR interior interpolation between that fixed knot and the point being
//   solved — same reasoning as bootstrap_cash_deposit's gap_frac. These periods
//   cannot be folded into annuity_const and are passed as parallel vectors:
//     gap_dc_fracs[i], gap_t_todays[i]  — this period's dc frac and dc_int(today, pay_i)
//     gap_fracs[i]                      — interpolation fraction toward x
//     r_fixed                           — rate at the last fixed knot (shared by all gap periods)
//==
inline void bootstrap_swap(
    BDateCurve& curve,
    int    bot_ord,
    int    last_pay_ord,
    double t_today_last,
    double annuity_const,
    double last_dc_frac,
    double df_spot,
    int    comp,
    double quote,
    double lo, double hi, double xtol,
    const std::vector<double>& gap_dc_fracs = {},
    const std::vector<double>& gap_t_todays = {},
    const std::vector<double>& gap_fracs    = {},
    double r_fixed = 0.0
) {
    auto f = [&](double x) -> double {
        double acc_last  = compounding_apply(comp, BCompoundTransform::RATE_TO_ACCRUAL, t_today_last, x);
        double df_last   = 1.0 / acc_last;
        double annuity   = annuity_const + last_dc_frac * df_last;
        for (size_t i = 0; i < gap_dc_fracs.size(); ++i) {
            double r_i   = r_fixed + gap_fracs[i] * (x - r_fixed);
            double acc_i = compounding_apply(comp, BCompoundTransform::RATE_TO_ACCRUAL, gap_t_todays[i], r_i);
            annuity     += gap_dc_fracs[i] / acc_i;
        }
        return (df_spot - df_last) / annuity - quote;
    };
    double root = brent_solve(f, lo, hi, xtol);
    bcurve_update(curve, last_pay_ord, root);
    if (curve.size() < 3)
        bcurve_update(curve, bot_ord, root);
}
