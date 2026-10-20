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
#   include <pwd.h>

bool OsUser::get_user_name(std::string& user_name) {
    passwd* pw = getpwuid(geteuid());
    if (!pw)
        return false;
    user_name = pw->pw_name;
    return true;
}
#endif

OsUser OsUser::me;