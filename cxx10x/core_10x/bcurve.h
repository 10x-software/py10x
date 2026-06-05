#pragma once

#include <vector>
#include <limits>
#include <cmath>
#include <algorithm>
#include <pybind11/pybind11.h>

#include "py_linkage.h"

namespace py = pybind11;

inline constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

//==
//   Enums
//==

enum class IPKind {
    NO_INTERP  = 0,
    ZERO       = 1,
    LINEAR     = 2,
    NEAREST    = 3,
    NEAREST_UP = 4,
    PREVIOUS   = 5,
    NEXT       = 6,
    SLINEAR    = 7,
    QUADRATIC  = 8,
    CUBIC      = 9,
};

enum class Extrap { LINEAR, FLAT };

//==
//   CurveTemplate
//==

template<typename time_type>
class CurveTemplate {
public:
    using TIMES = std::vector<time_type>;
    using VALUES = std::vector<double>;
    
    CurveTemplate() = default;
    CurveTemplate(TIMES times, VALUES values)
    : m_times(std::move(times)), m_values(std::move(values))
    {
        if (m_times.size() != m_values.size())
            throw py::value_error("CurveTemplate: times and values must have the same length");
    }

    void set_times(TIMES times) {
        m_times = std::move(times);
    }

    void set_values(VALUES values) {
        m_values = std::move(values);
    }

    void update(time_type t, double v) {
        auto it = std::lower_bound(m_times.begin(), m_times.end(), t);
        if (it != m_times.end() && *it == t) {
            m_values[it - m_times.begin()] = v;
        } else {
            auto idx = it - m_times.begin();
            m_times.insert(it, t);
            m_values.insert(m_values.begin() + idx, v);
        }
    }

    void update_many(const TIMES& times, const VALUES& values) {
        if (times.size() != values.size())
            throw py::value_error("CurveTemplate: times and values must have the same length");

        for (size_t i = 0; i < times.size(); ++i)
            update(times[i], values[i]);
    }

    bool remove(time_type t) {
        auto it = std::lower_bound(m_times.begin(), m_times.end(), t);
        if (it == m_times.end() || *it != t)
            return false;

        auto idx = it - m_times.begin();
        m_times.erase(it);
        m_values.erase(m_values.begin() + idx);
        return true;
    }
    
    [[nodiscard]] double value(time_type t) const {
        const int n = size();

        //-- NO_INTERP: exact binary search, NaN if not found
        if (m_ip_kind == IPKind::NO_INTERP) {
            auto it = std::lower_bound(m_times.begin(), m_times.end(), t);
            if (it != m_times.end() && *it == t)
                return m_values[it - m_times.begin()];
            return kNaN;
        }

        //-- Not enough points: exact match if possible, else throw
        if (n < min_points(m_ip_kind)) {
            auto it = std::lower_bound(m_times.begin(), m_times.end(), t);
            if (it != m_times.end() && *it == t)
                return m_values[it - m_times.begin()];
            throw py::value_error("CurveTemplate: not enough data points for interpolation");
        }

        //-- beginning_of_time guard
        if (m_has_bot && t < m_bot)
            return kNaN;

        auto td  = static_cast<double>(t);
        auto t0  = static_cast<double>(m_times[0]);
        auto tn  = static_cast<double>(m_times[n - 1]);

        //-- Left extrapolation
        if (td < t0) {
            switch (m_ip_kind) {
                case IPKind::PREVIOUS: case IPKind::ZERO:
                case IPKind::NEXT:     case IPKind::NEAREST: case IPKind::NEAREST_UP:
                    return m_values[0];
                default: break;
            }
            if (m_extrap == Extrap::FLAT)
                return m_left_fill;
            
            auto dt = static_cast<double>(m_times[1]) - t0;
            if (dt == 0.0) 
                return m_values[0];
            
            return m_values[0] + (td - t0) / dt * (m_values[1] - m_values[0]);
        }

        //-- Right extrapolation
        if (td > tn) {
            switch (m_ip_kind) {
                case IPKind::PREVIOUS: case IPKind::ZERO:
                case IPKind::NEXT:     case IPKind::NEAREST: case IPKind::NEAREST_UP:
                    return m_values[n - 1];
                default: break;
            }
            if (m_extrap == Extrap::FLAT)
                return m_right_fill;
            
            auto dt = tn - static_cast<double>(m_times[n - 2]);
            if (dt == 0.0) 
                return m_values[n - 1];
            
            return m_values[n - 1] + (td - tn) / dt * (m_values[n - 1] - m_values[n - 2]);
        }

        //-- Interior interpolation
        switch (m_ip_kind) {
            case IPKind::LINEAR: case IPKind::SLINEAR: {
                int lo = 0, hi = n - 1;
                while (lo + 1 < hi) {
                    int mid = (lo + hi) >> 1;
                    if (static_cast<double>(m_times[mid]) <= td) 
                        lo = mid;
                    else 
                        hi = mid;
                }
                auto dt = static_cast<double>(m_times[hi]) - static_cast<double>(m_times[lo]);
                if (dt == 0.0) 
                    return m_values[lo];
                
                return m_values[lo] + (td - static_cast<double>(m_times[lo])) / dt * (m_values[hi] - m_values[lo]);
            }
            case IPKind::PREVIOUS: case IPKind::ZERO: {
                auto it = std::upper_bound(m_times.begin(), m_times.end(), t) - 1;
                return m_values[it - m_times.begin()];
            }
            case IPKind::NEXT: {
                auto it = std::lower_bound(m_times.begin(), m_times.end(), t);
                return m_values[it - m_times.begin()];
            }
            case IPKind::NEAREST: {
                auto hi_it = std::lower_bound(m_times.begin(), m_times.end(), t);
                if (hi_it == m_times.begin()) 
                    return m_values[0];
                
                int hi = static_cast<int>(hi_it - m_times.begin());
                if (*hi_it == t) 
                    return m_values[hi];
                
                int lo = hi - 1;
                auto dl = td - static_cast<double>(m_times[lo]);
                auto dr = static_cast<double>(m_times[hi]) - td;
                return (dl <= dr) ? m_values[lo] : m_values[hi];
            }
            case IPKind::NEAREST_UP: {
                auto hi_it = std::lower_bound(m_times.begin(), m_times.end(), t);
                if (hi_it == m_times.begin())
                    return m_values[0];
                
                int hi = static_cast<int>(hi_it - m_times.begin());
                if (*hi_it == t) 
                    return m_values[hi];
                
                int lo = hi - 1;
                auto dl = td - static_cast<double>(m_times[lo]);
                auto dr = static_cast<double>(m_times[hi]) - td;
                return (dl < dr) ? m_values[lo] : m_values[hi];
            }
            default:
                throw py::value_error("CurveTemplate: interpolation kind not yet implemented");
        }

    }
    void set_ip_kind(IPKind kind)               { m_ip_kind = kind; }
    void set_beginning_of_time(time_type bot)   { m_bot = bot; m_has_bot = true; }
    void clear_beginning_of_time()              { m_has_bot = false; }
    void set_linear()                           { m_extrap = Extrap::LINEAR; }
    
    void set_flat(double left_fill, double right_fill) {
        m_extrap     = Extrap::FLAT;
        m_left_fill  = left_fill;
        m_right_fill = right_fill;
    }

    [[nodiscard]] const TIMES&  times()  const          { return m_times; }
    [[nodiscard]] const VALUES& values() const          { return m_values; }
    [[nodiscard]] int   size() const                    { return static_cast<int>(m_times.size()); }
    [[nodiscard]] bool  has_beginning_of_time() const   { return m_has_bot; }
    [[nodiscard]] time_type beginning_of_time() const   { return m_bot; }

protected:
    static int min_points(IPKind kind) {
        switch (kind) {
            case IPKind::NO_INTERP:  return 0;
            case IPKind::ZERO:       return 1;
            case IPKind::QUADRATIC:  return 3;
            case IPKind::CUBIC:      return 4;
            default:                 return 2;
        }
    }

    TIMES       m_times;
    VALUES      m_values;
    IPKind      m_ip_kind    = IPKind::LINEAR;
    Extrap      m_extrap     = Extrap::LINEAR;
    double      m_left_fill  = kNaN;
    double      m_right_fill = kNaN;
    bool        m_has_bot    = false;
    time_type   m_bot        = time_type{};
};

//==
//   Type aliases
//==

using BCurve = CurveTemplate<double>;

//==
//   BDateCurve
//==

class BDateCurve : public CurveTemplate<int> {
public:
    BDateCurve() = default;
    BDateCurve(std::vector<int> times, std::vector<double> values)
        : CurveTemplate<int>(std::move(times), std::move(values)) {}

    void update(const py::object& d, double v);
    void update_many(const py::list& dates, const VALUES& values);
    bool remove(const py::object& d);
    void set_beginning_of_time(const py::object& d);

    [[nodiscard]] py::object start_time() const {
        return size() > 0 ? PyLinkage::fromordinal(m_times[0]) : py::none();
    }

    [[nodiscard]] py::object end_time() const {
        auto n = size();
        return n > 0 ? PyLinkage::fromordinal(m_times[n-1]) : py::none();
    }

    [[nodiscard]] double value(const py::object& d) const;
    [[nodiscard]] py::object beginning_of_time_as_date() const;
    [[nodiscard]] py::list dates() const;
    [[nodiscard]] py::list dates_values(py::object min_date = py::none(), py::object max_date = py::none()) const;
};
