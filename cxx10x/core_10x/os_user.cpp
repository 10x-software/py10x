//
// Created by AMD on 3/12/2025.
//

#include "os_user.h"

#ifdef _WIN32
#   include <windows.h>
#   include <Lmcons.h>
bool OsUser::get_user_name(std::string& user_name) {
    char username[UNLEN + 1];
    DWORD size = sizeof(username);
    auto rc = GetUserNameA(username, &size);
    if (!rc)
        return false;

    user_name = username;
    return true;
}
#elif defined(__unix__) || defined(__APPLE__) || defined(__linux)
#   include <unistd.h>
#   include <stdlib.h>
    bool OsUser::get_user_name(std::string& user_name) {
        const char* username = getenv("USER");
        if (!username) {
            username = getenv("LOGNAME");
            if (!username)
                return false;
        }

        user_name = username;
        return true;
    }
#endif

OsUser OsUser::me;