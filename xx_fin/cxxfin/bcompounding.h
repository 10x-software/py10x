#pragma once

#include <cmath>

struct BCompounding {
    static constexpr int SIMPLE      = 0;
    static constexpr int ANNUAL      = 1;
    static constexpr int SEMI_ANNUAL = 2;
    static constexpr int QUARTERLY   = 3;
    static constexpr int MONTHLY     = 4;
    static constexpr int WEEKLY      = 5;
    static constexpr int CONTINUOUS  = 6;
};

struct BCompoundTransform {
    static constexpr int RATE_TO_ACCRUAL = 0;
    static constexpr int ACCRUAL_TO_RATE = 1;
};

namespace bcompounding_detail {

using CompFn = double(*)(double t, double v);

//-- (t, r) -> accrual factor
inline double simple_r2a(double t, double r) { return 1.0 + r * t; }
inline double annual_r2a(double t, double r) { return std::pow(1.0 + r,        t       ); }
inline double semi_r2a  (double t, double r) { return std::pow(1.0 + r /  2.0, t *  2.0); }
inline double qrtr_r2a  (double t, double r) { return std::pow(1.0 + r /  4.0, t *  4.0); }
inline double mnth_r2a  (double t, double r) { return std::pow(1.0 + r / 12.0, t * 12.0); }
inline double wkly_r2a  (double t, double r) { return std::pow(1.0 + r / 52.0, t * 52.0); }
inline double cont_r2a  (double t, double r) { return std::exp(r * t); }

//-- (t, a) -> rate
inline double simple_a2r(double t, double a) { return t ? (a - 1.0) / t : 0.0; }
inline double annual_a2r(double t, double a) { return t ? std::pow(a, 1.0 / t        ) - 1.0           : 0.0; }
inline double semi_a2r  (double t, double a) { return t ? (std::pow(a, 1.0 / (t *  2.0)) - 1.0) *  2.0 : 0.0; }
inline double qrtr_a2r  (double t, double a) { return t ? (std::pow(a, 1.0 / (t *  4.0)) - 1.0) *  4.0 : 0.0; }
inline double mnth_a2r  (double t, double a) { return t ? (std::pow(a, 1.0 / (t * 12.0)) - 1.0) * 12.0 : 0.0; }
inline double wkly_a2r  (double t, double a) { return t ? (std::pow(a, 1.0 / (t * 52.0)) - 1.0) * 52.0 : 0.0; }
inline double cont_a2r  (double t, double a) { return t ? std::log(a) / t : 0.0; }

} // namespace bcompounding_detail

//-- [BCompounding index][BCompoundTransform index]
inline double compounding_apply(int comp, int transform, double t, double v) {
    using namespace bcompounding_detail;
    static const CompFn matrix[][2] = {
        { simple_r2a, simple_a2r },  // SIMPLE
        { annual_r2a, annual_a2r },  // ANNUAL
        { semi_r2a,   semi_a2r   },  // SEMI_ANNUAL
        { qrtr_r2a,   qrtr_a2r   },  // QUARTERLY
        { mnth_r2a,   mnth_a2r   },  // MONTHLY
        { wkly_r2a,   wkly_a2r   },  // WEEKLY
        { cont_r2a,   cont_a2r   },  // CONTINUOUS
    };
    return matrix[comp][transform](t, v);
}
