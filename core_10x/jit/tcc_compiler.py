import sys
import ctypes
from pathlib import Path
import tccbox
import struct
import re

from core_10x.global_cache import cache

#== TCC — thin ctypes wrapper around libtcc (from tccbox)


class _InMemBinary:
    """Holds a TCC-compiled in-memory binary. Must stay alive as long as the code is called.

    tcc_delete is intentionally NOT called: Cython module objects (types, functions) live in TCC
    memory and are referenced by Python's runtime until process exit. Calling tcc_delete while
    those objects are still alive causes an access violation during Python shutdown. TCC memory
    is reclaimed by the OS when the process exits.
    """

    def __init__(self, lib: ctypes.CDLL, binary_handle: int):
        self._lib           = lib
        self._binary_handle = binary_handle   #-- opaque pointer to the compiled in-memory binary

    def symbol(self, name: str) -> int:
        ptr = self._lib.tcc_get_symbol(self._binary_handle, name.encode())
        if not ptr:
            raise KeyError(f"TCC: symbol not found: '{name}'")
        return ptr

class TCC:
    _OUTPUT_MEMORY = 1
    _RELOCATE_AUTO = ctypes.c_void_p(1)

    s_lib = None
    @classmethod
    @cache
    def _init(cls):
        lib_dir = Path(tccbox.tcc_lib_dir())
        if sys.platform == 'win32':
            dll_name = 'libtcc.dll'
        elif sys.platform == 'darwin':
            dll_name = 'libtcc.dylib'
        else:
            dll_name = 'libtcc.so'
        dll_path = lib_dir / dll_name
        if not dll_path.exists():
            raise FileNotFoundError(f"libtcc not found at {dll_path}")

        cls.s_lib = ctypes.CDLL(str(dll_path))
        cls._setup_api()

    @classmethod
    def _setup_api(cls):
        L  = cls.s_lib
        vp = ctypes.c_void_p
        ci = ctypes.c_int
        cs = ctypes.c_char_p

        def bind(name, restype, *argtypes):
            f = getattr(L, name)
            f.restype  = restype
            f.argtypes = list(argtypes)

        bind('tcc_new',              vp)
        bind('tcc_delete',           None, vp)
        bind('tcc_set_output_type',  None, vp, ci)
        bind('tcc_add_include_path', ci,   vp, cs)
        bind('tcc_add_library_path', ci,   vp, cs)
        bind('tcc_add_library',      ci,   vp, cs)
        bind('tcc_set_options',      ci,   vp, cs)
        bind('tcc_define_symbol',    None, vp, cs, cs)
        bind('tcc_set_error_func',   None, vp, vp, ctypes.c_void_p)
        bind('tcc_add_symbol',       None, vp, cs, vp)
        bind('tcc_compile_string',   ci,   vp, cs)
        bind('tcc_relocate',         ci,   vp, vp)
        bind('tcc_get_symbol',       vp,   vp, cs)

    #-- size defines that Cython-generated C checks at compile time (pyconfig.h may not be read correctly by TCC)
    _SIZE_DEFINES: dict[str, int] = {
        'SIZEOF_VOID_P':   struct.calcsize('P'),
        'SIZEOF_INT':      struct.calcsize('i'),
        'SIZEOF_LONG':     struct.calcsize('l'),
        'SIZEOF_LONG_LONG': struct.calcsize('q'),
        'SIZEOF_SIZE_T':   struct.calcsize('P'),
        'SIZEOF_SHORT':    struct.calcsize('h'),
    }

    @classmethod
    def compile(
        cls,
        c_source:     str,
        include_dirs: list[str] = (),
        lib_dirs:     list[str] = (),
        libs:         list[str] = (),
        lib_files:    list[str] = (),   #-- full paths to .lib/.a files, bypasses -l name resolution
    ) -> _InMemBinary:
        cls._init()

        L      = cls.s_lib
        state  = L.tcc_new()
        errors: list[str] = []

        if not state:
            raise RuntimeError('tcc_new() returned NULL')

        #-- capture TCC error messages via callback
        _ErrorFunc = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)
        def _on_error(opaque, msg):
            errors.append(msg.decode(errors='replace') if msg else '')
        error_cb = _ErrorFunc(_on_error)   #-- keep alive for the duration
        L.tcc_set_error_func(state, None, error_cb)

        try:
            if struct.calcsize('P') == 8:
                L.tcc_set_options(state, b'-m64')
            L.tcc_set_output_type(state, cls._OUTPUT_MEMORY)
            for sym, val in cls._SIZE_DEFINES.items():
                L.tcc_define_symbol(state, sym.encode(), str(val).encode())
            for d in include_dirs:
                L.tcc_add_include_path(state, d.encode())
            for d in lib_dirs:
                L.tcc_add_library_path(state, d.encode())
            for lib in libs:
                L.tcc_add_library(state, lib.encode())
            for f in lib_files:
                L.tcc_add_file(state, f.encode())

            rc = L.tcc_compile_string(state, c_source.encode())
            if rc != 0:
                msg = '\n'.join(errors)
                context = _tcc_error_context(c_source, errors)
                raise RuntimeError(f'TCC compile failed:\n{msg}{context}')

            #-- inject Python C API symbols from the already-loaded DLL
            if sys.platform == 'win32':
                dll_name = f'python{sys.version_info.major}{sys.version_info.minor}.dll'
                _inject_dll_exports(L, state, dll_name)

            rc = L.tcc_relocate(state, cls._RELOCATE_AUTO)
            if rc != 0:
                raise RuntimeError('TCC relocate failed:\n' + '\n'.join(errors))

            return _InMemBinary(L, binary_handle=state)
        except Exception:
            L.tcc_delete(state)
            raise

def _tcc_error_context(c_source: str, errors: list[str], radius: int = 3) -> str:
    """Extract source lines around line numbers mentioned in TCC error messages."""
    src_lines = c_source.split('\n')
    seen: set[int] = set()
    snippets: list[str] = []
    for msg in errors:
        m = re.search(r'<string>:(\d+):', msg)
        if m:
            lineno = int(m.group(1)) - 1   #-- 0-based
            if lineno in seen:
                continue
            seen.add(lineno)
            lo = max(0, lineno - radius)
            hi = min(len(src_lines), lineno + radius + 1)
            block = []
            for i in range(lo, hi):
                marker = '=>' if i == lineno else '  '
                block.append(f'  {marker} {i+1:4d}: {src_lines[i]}')
            snippets.append('\n'.join(block))
    return ('\n\nC source context:\n' + '\n---\n'.join(snippets)) if snippets else ''

def _inject_dll_exports(L: ctypes.CDLL, state: int, dll_name: str) -> int:
    """
    Walk the PE export table of an already-loaded DLL and inject every
    exported symbol into TCC via tcc_add_symbol.
    Returns the number of symbols injected.
    """
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.GetModuleHandleA.restype  = ctypes.c_void_p
    k32.GetModuleHandleA.argtypes = [ctypes.c_char_p]

    base = k32.GetModuleHandleA(dll_name.encode())
    if not base:
        raise RuntimeError(f'GetModuleHandle failed for {dll_name}')

    #-- DOS header → PE offset
    pe_off  = ctypes.c_uint32.from_address(base + 0x3C).value
    if ctypes.c_uint32.from_address(base + pe_off).value != 0x4550:   #-- "PE\0\0"
        raise RuntimeError(f'{dll_name}: not a valid PE image')

    #-- Optional header: magic tells us PE32 vs PE32+
    opt_off = base + pe_off + 24
    magic   = ctypes.c_uint16.from_address(opt_off).value
    dd_off  = opt_off + (112 if magic == 0x020B else 96)   #-- DataDirectory[0] = export dir

    export_rva = ctypes.c_uint32.from_address(dd_off).value
    if not export_rva:
        return 0

    exp = base + export_rva
    num_names    = ctypes.c_uint32.from_address(exp + 24).value
    funcs_rva    = ctypes.c_uint32.from_address(exp + 28).value
    names_rva    = ctypes.c_uint32.from_address(exp + 32).value
    ordinals_rva = ctypes.c_uint32.from_address(exp + 36).value

    count = 0
    for i in range(num_names):
        name_rva  = ctypes.c_uint32.from_address(base + names_rva    + i * 4).value
        sym_name  = ctypes.string_at(base + name_rva).decode('ascii', errors='replace')
        ordinal   = ctypes.c_uint16.from_address(base + ordinals_rva + i * 2).value
        func_rva  = ctypes.c_uint32.from_address(base + funcs_rva    + ordinal * 4).value
        L.tcc_add_symbol(state, sym_name.encode(), ctypes.c_void_p(base + func_rva))
        count += 1

    return count
