if __name__ == '__main__':

    from core_10x.jit.trait_getter_cython_compiler import CythonCompiler, FuncTreeWalker
    from core_10x.jit.manual_tests.basic_test import Calc

    cc = CythonCompiler.instance(Calc, 'price')

    #cy_text = cc.generate_cython_source()
    c_src = cc.generate_c_source()

