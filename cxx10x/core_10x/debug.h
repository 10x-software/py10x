//
// Created by IAP on 12/10/25.
//

#ifndef INC_10X_I_DEBUG_H
#define INC_10X_I_DEBUG_H
#include <backward.hpp>
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