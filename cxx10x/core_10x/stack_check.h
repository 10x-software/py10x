#pragma once

//-- Raises RecursionError when this thread's C stack is nearly used up; called before the kernel calls back into user code.
//-- Until 3.14 Python limits the number of frames, not their size, and the kernel's frames can use up a small stack first
//-- (the Windows default, a thread with its own stack size).
void check_stack();
