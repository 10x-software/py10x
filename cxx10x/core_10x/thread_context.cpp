#include "thread_context.h"

ThreadContext &ThreadContext::current_context() {
    thread_local ThreadContext ctx;
    return ctx;
}
