//
// Created by AMD on 28/06/2026.
//

#pragma once
#include <pybind11/pybind11.h>
#include <btraitable.h>
#include <bcurve.h>
#include "bcompounding.h"

class BRateCurve {
public:
    static double accrual(BTraitable* self, const py::object& d, py::object today) {
        auto* bcurve = self->get_value("bcurve").cast<BDateCurve*>();
        if (today.is_none()) {
            today = bcurve->beginning_of_time_as_date();
            if (today.is_none())
                throw py::value_error("beginning_of_time is not set");
        }
        if (PyObject_RichCompareBool(d.ptr(), today.ptr(), Py_EQ))
            return 1.0;
        double r = bcurve->value(d);
        auto t = self->get_value("dc_convention")(today, d).cast<double>();
        int    c = self->get_value("compounding").attr("value").cast<int>();
        return compounding_apply(c, BCompoundTransform::RATE_TO_ACCRUAL, t, r);
    }

    static double accrual_fwd(BTraitable* self, const py::object& d1, const py::object& d2, py::object today) {
        if (PyObject_RichCompareBool(d1.ptr(), d2.ptr(), Py_EQ))
            return 1.0;

        auto* bcurve = self->get_value("bcurve").cast<BDateCurve*>();
        if (today.is_none()) {
            today = bcurve->beginning_of_time_as_date();
            if (today.is_none())
                throw py::value_error("beginning_of_time is not set");
        }

        py::object dcc = self->get_value("dc_convention");
        int c = self->get_value("compounding").attr("value").cast<int>();

        auto accrual_at = [&](const py::object& d) -> double {
            if (PyObject_RichCompareBool(d.ptr(), today.ptr(), Py_EQ)) return 1.0;
            return compounding_apply(c, BCompoundTransform::RATE_TO_ACCRUAL,
                                     dcc(today, d).cast<double>(), bcurve->value(d));
        };

        bool d1_le_d2 = PyObject_RichCompareBool(d1.ptr(), d2.ptr(), Py_LE) != 0;
        return accrual_at(d1_le_d2 ? d2 : d1) / accrual_at(d1_le_d2 ? d1 : d2);
    }

    static double discount_factor(BTraitable* self, const py::object& d, py::object today) {
        return 1.0 / accrual(self, d, std::move(today));
    }

    static double discount_factor_fwd(BTraitable* self, const py::object& d1, const py::object& d2, py::object today) {
        if (today.is_none()) {
            today = self->get_value("bcurve").cast<BDateCurve*>()->beginning_of_time_as_date();
            if (today.is_none())
                throw py::value_error("beginning_of_time is not set");
        }
        return discount_factor(self, d2, today) / discount_factor(self, d1, today);
    }
};
