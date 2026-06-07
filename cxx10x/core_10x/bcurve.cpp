#include "bcurve.h"
#include "py_linkage.h"

//==
//   BDateCurve
//==

void BDateCurve::update(const py::object& d, double v) {
    CurveTemplate<int>::update(PyLinkage::toordinal(d), v);
}

void BDateCurve::update_many(const py::list& dates, const BDateCurve::VALUES& values) {
    if (dates.size() != values.size())
        throw py::value_error("BDateCurve: dates and values must have the same length");

    size_t i = 0;
    for (py::handle h : dates)
        update(py::reinterpret_borrow<py::object>(h), values[i++]);
}

bool BDateCurve::remove(const py::object& d) {
    return CurveTemplate<int>::remove(PyLinkage::toordinal(d));
}

double BDateCurve::value(const py::object& d) const {
    return CurveTemplate<int>::value(PyLinkage::toordinal(d));
}

void BDateCurve::set_beginning_of_time(const py::object& d) {
    CurveTemplate<int>::set_beginning_of_time(PyLinkage::toordinal(d));
}

py::object BDateCurve::beginning_of_time_as_date() const {
    auto bot = CurveTemplate<int>::beginning_of_time();
    return PyLinkage::fromordinal(bot);
}

py::list BDateCurve::dates() const {
    py::list result;
    for (int t : CurveTemplate<int>::times())
        result.append(PyLinkage::fromordinal(t));
    return result;
}

py::list BDateCurve::dates_values(py::object min_date, py::object max_date) const {
    int min_ord = min_date.is_none() ? std::numeric_limits<int>::min() : PyLinkage::toordinal(min_date);
    int max_ord = max_date.is_none() ? std::numeric_limits<int>::max() : PyLinkage::toordinal(max_date);

    py::list result;
    const auto& ts = CurveTemplate<int>::times();
    const auto& vs = CurveTemplate<int>::values();
    for (size_t i = 0; i < ts.size(); ++i) {
        if (ts[i] >= min_ord && ts[i] <= max_ord)
            result.append(py::make_tuple(PyLinkage::fromordinal(ts[i]), vs[i]));
    }
    return result;
}
