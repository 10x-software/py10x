#pragma once

#include <chrono>
#include <pybind11/pybind11.h>
#include <datetime.h>

namespace py = pybind11;

//-- Type caster: Python datetime.date <-> std::chrono::year_month_day
//
//   load()  uses PyDate_Check + PyDateTime_GET_* macros — direct C struct reads, zero Python overhead.
//   cast()  uses PyDate_FromDate — likewise a direct C API call, no attribute lookup.
//   PyDateTime_IMPORT is called once (static) on first use to populate PyDateTimeAPI.

namespace pybind11 { namespace detail {

template <>
class type_caster<std::chrono::year_month_day> {
public:
    PYBIND11_TYPE_CASTER(std::chrono::year_month_day, const_name("datetime.date"));

    type_caster() : value{} {}

    bool load(handle src, bool) {
        static const bool dt_imported = (PyDateTime_IMPORT, true);
        (void)dt_imported;

        if (!PyDate_Check(src.ptr()))
            return false;

        value = std::chrono::year_month_day {
            std::chrono::year  (PyDateTime_GET_YEAR (src.ptr())),
            std::chrono::month (PyDateTime_GET_MONTH(src.ptr())),
            std::chrono::day   (PyDateTime_GET_DAY  (src.ptr()))
        };
        return true;
    }

    static handle cast(std::chrono::year_month_day src, return_value_policy, handle) {
        return PyDate_FromDate(
            (int)      src.year(),
            (unsigned) src.month(),
            (unsigned) src.day()
        );
    }
};

}} // namespace pybind11::detail

//-- Helpers

namespace bdc_detail {

using Date     = std::chrono::year_month_day;
using sys_days = std::chrono::sys_days;

inline int days_between(Date d1, Date d2) {
    return (sys_days(d2) - sys_days(d1)).count();
}

inline int year_num_days(int y) {
    using namespace std::chrono;
    return (sys_days(year(y) / December / 31) - sys_days(year(y) / January / 1)).count() + 1;
}

} // namespace bdc_detail

//-- BDayCountConvention
//   Usage: BDayCountConvention::ACT365(date_from, date_to) -> double

struct BDayCountConvention {
    using Date = std::chrono::year_month_day;

    static double ACT360(Date d1, Date d2) {
        return bdc_detail::days_between(d1, d2) / 360.0;
    }

    //-- TODO: according to ISDA (check!): Act/365 is ActAct, ACT/365Fixed (ACT/365F, ACT/365.Fixed) is Act365
    static double ACT365(Date d1, Date d2) {
        return bdc_detail::days_between(d1, d2) / 365.0;
    }

    static double ACTACT(Date d1, Date d2) {
        using namespace std::chrono;
        using namespace bdc_detail;

        int fy = (int)d1.year();
        int ty = (int)d2.year();

        int fy_days = year_num_days(fy);

        if (fy == ty)
            return days_between(d1, d2) / (double)fy_days;

        int ty_days = year_num_days(ty);

        // days remaining in start/end year via next Jan 1 (Dec 31 deltas undercount by 1)
        Date fy_next { year(fy + 1), January, day(1) };
        Date ty_next { year(ty + 1), January, day(1) };

        double frac1 = days_between(d1, fy_next) / (double)fy_days;
        double frac2 = days_between(d2, ty_next) / (double)ty_days;

        return (frac1 - frac2) + (ty - fy);
    }

    static double BB30360(Date d1, Date d2) {
        int fd = (unsigned)d1.day(),   td = (unsigned)d2.day();
        int fm = (unsigned)d1.month(), tm = (unsigned)d2.month();
        int fy = (int)d1.year(),       ty = (int)d2.year();

        if (fd == 31) fd = 30;
        if (td == 31 && fd >= 30) td = 30;

        return (ty - fy) + (tm - fm) / 12.0 + (td - fd) / 360.0;
    }

    static double US30360(Date d1, Date d2) {
        using namespace std::chrono;

        int fd = (unsigned)d1.day(),   td = (unsigned)d2.day();
        int fm = (unsigned)d1.month(), tm = (unsigned)d2.month();
        int fy = (int)d1.year(),       ty = (int)d2.year();

        if (d1 == d1.year() / d1.month() / last) fd = 30;
        if (td == 31 && fd >= 30) td = 30;

        return (ty - fy) + (tm - fm) / 12.0 + (td - fd) / 360.0;
    }

    //-- Eurobond basis, a.k.a. 30E/360 in Bloomberg (cbonds.com/glossary/30e-360)
    //-- Most of European IBORs are probably EB30360
    static double EB30360(Date d1, Date d2) {
        int fd = (unsigned)d1.day(),   td = (unsigned)d2.day();
        int fm = (unsigned)d1.month(), tm = (unsigned)d2.month();
        int fy = (int)d1.year(),       ty = (int)d2.year();

        if (fd == 31) fd = 30;
        if (td == 31) td = 30;

        return (ty - fy) + (tm - fm) / 12.0 + (td - fd) / 360.0;
    }
};
