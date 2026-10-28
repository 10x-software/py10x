#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <numeric>
#include <btraitable.h>

#include "bday_count_convention.h"
#include "bcompounding.h"
#include "brate_curve.h"
#include "bzrc_bootstrap.h"

namespace py = pybind11;

class BSampleTraitable {
public:
    static py::object trait3_get(BTraitable* self) {
        return self->get_value("trait1") * self->get_value("trait2");
    }
};

static long long product(const std::vector<long long>& values)
{
    return std::accumulate(values.begin(), values.end(), 1LL, std::multiplies<long long>());
}

PYBIND11_MODULE(cxxfin, m)
{
    m.doc() = "XX Financial Domain C++ extension";
    m.attr("__version__") =
        #ifdef VERSION_INFO
            VERSION_INFO
        #else
            "unknown"
        #endif
        ;

    m.def("product", &product, py::arg("values"),
          "Return the product of all integers in the list.");

    py::class_<BSampleTraitable>(m, "BSampleTraitable")
        .def("trait3_get", &BSampleTraitable::trait3_get);

    py::object dcc = py::module_::import("builtins").attr("type")(
        "BDayCountConvention", py::make_tuple(), py::dict()
    );
    m.attr("BDayCountConvention") = dcc;
    dcc.attr("ACT360")  = py::cpp_function(&BDayCountConvention::ACT360,  py::name("ACT360"));
    dcc.attr("ACT365")  = py::cpp_function(&BDayCountConvention::ACT365,  py::name("ACT365"));
    dcc.attr("ACTACT")  = py::cpp_function(&BDayCountConvention::ACTACT,  py::name("ACTACT"));
    dcc.attr("BB30360") = py::cpp_function(&BDayCountConvention::BB30360, py::name("BB30360"));
    dcc.attr("US30360") = py::cpp_function(&BDayCountConvention::US30360, py::name("US30360"));
    dcc.attr("EB30360") = py::cpp_function(&BDayCountConvention::EB30360, py::name("EB30360"));

    py::object bc = py::module_::import("builtins").attr("type")(
        "BCompounding", py::make_tuple(), py::dict()
    );
    m.attr("BCompounding") = bc;
    bc.attr("SIMPLE")      = py::int_(BCompounding::SIMPLE);
    bc.attr("ANNUAL")      = py::int_(BCompounding::ANNUAL);
    bc.attr("SEMI_ANNUAL") = py::int_(BCompounding::SEMI_ANNUAL);
    bc.attr("QUARTERLY")   = py::int_(BCompounding::QUARTERLY);
    bc.attr("MONTHLY")     = py::int_(BCompounding::MONTHLY);
    bc.attr("WEEKLY")      = py::int_(BCompounding::WEEKLY);
    bc.attr("CONTINUOUS")  = py::int_(BCompounding::CONTINUOUS);

    py::object bct = py::module_::import("builtins").attr("type")(
        "BCompoundTransform", py::make_tuple(), py::dict()
    );
    m.attr("BCompoundTransform") = bct;
    bct.attr("RATE_TO_ACCRUAL") = py::int_(BCompoundTransform::RATE_TO_ACCRUAL);
    bct.attr("ACCRUAL_TO_RATE") = py::int_(BCompoundTransform::ACCRUAL_TO_RATE);

    m.def("compounding_apply", &compounding_apply,
          py::arg("comp"), py::arg("transform"), py::arg("t"), py::arg("v"));

    auto comp_to_int = [bc](const py::object& comp) -> int {
        return bc.attr(comp.attr("name").cast<std::string>().c_str()).cast<int>();
    };

    m.def("bootstrap_cash_deposit",
          [comp_to_int](BDateCurve& curve, int bot_ord, int end_ord,
             double acc_start, double t_today_end, double t_start_end,
             py::object comp, py::object quot_comp,
             double quote, double lo, double hi, double xtol,
             double t_today_start, double gap_frac, double r_fixed) {
              bootstrap_cash_deposit(curve, bot_ord, end_ord,
                                     acc_start, t_today_end, t_start_end,
                                     comp_to_int(comp), comp_to_int(quot_comp),
                                     quote, lo, hi, xtol,
                                     t_today_start, gap_frac, r_fixed);
          },
          py::arg("curve"), py::arg("bot_ord"), py::arg("end_ord"),
          py::arg("acc_start"), py::arg("t_today_end"), py::arg("t_start_end"),
          py::arg("comp"), py::arg("quot_comp"),
          py::arg("quote"), py::arg("lo"), py::arg("hi"), py::arg("xtol"),
          py::arg("t_today_start") = 0.0, py::arg("gap_frac") = -1.0, py::arg("r_fixed") = 0.0);

    m.def("bootstrap_swap",
          [comp_to_int](BDateCurve& curve, int bot_ord, int last_pay_ord,
             py::object comp,
             double quote, double lo, double hi, double xtol,
             const std::vector<double>& dc_fracs,
             const std::vector<double>& df_starts, const std::vector<double>& t_starts, const std::vector<double>& g_starts,
             const std::vector<double>& df_ends,   const std::vector<double>& t_ends,   const std::vector<double>& g_ends,
             const std::vector<double>& df_pays,   const std::vector<double>& t_pays,   const std::vector<double>& g_pays,
             double r_fixed) {
              bootstrap_swap(curve, bot_ord, last_pay_ord,
                             comp_to_int(comp), quote, lo, hi, xtol,
                             dc_fracs,
                             df_starts, t_starts, g_starts,
                             df_ends, t_ends, g_ends,
                             df_pays, t_pays, g_pays,
                             r_fixed);
          },
          py::arg("curve"), py::arg("bot_ord"), py::arg("last_pay_ord"),
          py::arg("comp"),
          py::arg("quote"), py::arg("lo"), py::arg("hi"), py::arg("xtol"),
          py::arg("dc_fracs"),
          py::arg("df_starts"), py::arg("t_starts"), py::arg("g_starts"),
          py::arg("df_ends"), py::arg("t_ends"), py::arg("g_ends"),
          py::arg("df_pays"), py::arg("t_pays"), py::arg("g_pays"),
          py::arg("r_fixed"));

    py::class_<BRateCurve>(m, "BRateCurve")
        .def_static("accrual",             &BRateCurve::accrual,
                    py::arg("self"), py::arg("d"), py::arg("today") = py::none())
        .def_static("accrual_fwd",         &BRateCurve::accrual_fwd,
                    py::arg("self"), py::arg("d1"), py::arg("d2"), py::arg("today") = py::none())
        .def_static("discount_factor",     &BRateCurve::discount_factor,
                    py::arg("self"), py::arg("d"), py::arg("today") = py::none())
        .def_static("discount_factor_fwd", &BRateCurve::discount_factor_fwd,
                    py::arg("self"), py::arg("d1"), py::arg("d2"), py::arg("today") = py::none());
}
