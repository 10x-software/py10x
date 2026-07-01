//
// Created by IAP on 12/10/25.
//

#ifndef INC_10X_I_DEBUG_H
#define INC_10X_I_DEBUG_H
#if defined(_MSC_VER)
#  pragma warning(push)
#  pragma warning(disable: 4996) // backward.hpp uses getenv()
#endif
#include <backward.hpp>
#if defined(_MSC_VER)
#  pragma warning(pop)
#endif
#include <sstream>

inline std::string current_stacktrace()
{
    backward::StackTrace st;
    st.load_here();

    std::ostringstream oss;
    backward::Printer p;
    p.color_mode = backward::ColorMode::never;
    p.reverse = false;
    p.print(st, oss);     // ← this line works everywhere

    return oss.str();
}
#endif //INC_10X_I_DEBUG_H