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
//   Solves the delayed-payment par rate at curve[last_pay_ord] = x:
//     sum_i df(pay_i) * (df(start_i) / df(end_i) - 1) / annuity == quote
//   annuity = sum_i dc_frac_i * df(pay_i)
//
//   Accrual stops at end_i. pay_i is later, so this does not telescope to
//   df(spot) - df(last_pay).
//
//   No curve I/O inside the hot loop. For each period date the caller passes either
//   a constant discount factor (gap_frac < 0; the date is on or before the last
//   bootstrapped knot) or a linear interpolation toward x:
//     r = r_fixed + gap_frac * (x - r_fixed),   gap_frac in (0, 1]
//   gap_frac == 1 is the knot being solved (last_pay).
//==
inline double _bootstrap_df(
    double df_const, double t, double gap_frac,
    double x, double r_fixed, int comp
) {
    if (gap_frac < 0.0)
        return df_const;
    double r   = r_fixed + gap_frac * (x - r_fixed);
    double acc = compounding_apply(comp, BCompoundTransform::RATE_TO_ACCRUAL, t, r);
    return 1.0 / acc;
}

inline void bootstrap_swap(
    BDateCurve& curve,
    int    bot_ord,
    int    last_pay_ord,
    int    comp,
    double quote,
    double lo, double hi, double xtol,
    const std::vector<double>& dc_fracs,
    const std::vector<double>& df_starts, const std::vector<double>& t_starts, const std::vector<double>& g_starts,
    const std::vector<double>& df_ends,   const std::vector<double>& t_ends,   const std::vector<double>& g_ends,
    const std::vector<double>& df_pays,   const std::vector<double>& t_pays,   const std::vector<double>& g_pays,
    double r_fixed
) {
    const size_t n = dc_fracs.size();
    if (df_starts.size() != n || t_starts.size() != n || g_starts.size() != n ||
        df_ends.size()   != n || t_ends.size()   != n || g_ends.size()   != n ||
        df_pays.size()   != n || t_pays.size()   != n || g_pays.size()   != n)
        throw std::runtime_error("bootstrap_swap: period argument lengths differ");

    auto f = [&](double x) -> double {
        double float_pv = 0.0;
        double annuity  = 0.0;
        for (size_t i = 0; i < n; ++i) {
            double df_s = _bootstrap_df(df_starts[i], t_starts[i], g_starts[i], x, r_fixed, comp);
            double df_e = _bootstrap_df(df_ends[i],   t_ends[i],   g_ends[i],   x, r_fixed, comp);
            double df_p = _bootstrap_df(df_pays[i],   t_pays[i],   g_pays[i],   x, r_fixed, comp);
            annuity  += dc_fracs[i] * df_p;
            float_pv += df_p * (df_s / df_e - 1.0);
        }
        return float_pv / annuity - quote;
    };
    double root = brent_solve(f, lo, hi, xtol);
    bcurve_update(curve, last_pay_ord, root);
    if (curve.size() < 3)
        bcurve_update(curve, bot_ord, root);
}
