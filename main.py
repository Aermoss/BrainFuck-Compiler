import llvmlite.ir as ir
import llvmlite.binding as llvm

import os, sys, tempfile, subprocess, rsharp

def create_string(builder, string):
    fmt = bytearray((string + "\0").encode("utf-8"))
    c_str = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt)), fmt)
    ptr = builder.alloca(c_str.type)
    builder.store(c_str, ptr)
    return ptr

def compiler(builder, content):
    printf_func = ir.Function(builder.module, ir.FunctionType(ir.IntType(32), [], var_arg = True), "printf")
    getch_func = ir.Function(builder.module, ir.FunctionType(ir.IntType(8), [], var_arg = True), "getch")

    array_size = 1024
    array = ir.Constant(ir.ArrayType(ir.IntType(8), array_size), [0] * array_size)
    array_ptr = builder.alloca(array.type)
    builder.store(array, array_ptr)

    pointer = ir.Constant(ir.IntType(32), 0)
    pointer_ptr = builder.alloca(pointer.type)
    builder.store(pointer, pointer_ptr)

    for i in content:
        if i == "<": builder.store(builder.sub(builder.load(pointer_ptr), ir.Constant(ir.IntType(32), 1)), pointer_ptr)
        elif i == ">": builder.store(builder.add(builder.load(pointer_ptr), ir.Constant(ir.IntType(32), 1)), pointer_ptr)
        elif i == "+":
            tmp_ptr = builder.gep(array_ptr, [ir.Constant(ir.IntType(32), 0), builder.load(pointer_ptr)])
            builder.store(builder.add(builder.load(tmp_ptr), ir.Constant(ir.IntType(8), 1)), tmp_ptr)
        elif i == "-":
            tmp_ptr = builder.gep(array_ptr, [ir.Constant(ir.IntType(32), 0), builder.load(pointer_ptr)])
            builder.store(builder.sub(builder.load(tmp_ptr), ir.Constant(ir.IntType(8), 1)), tmp_ptr)
        elif i == ".": builder.call(printf_func, args = [create_string(builder, "%c"), builder.load(builder.gep(array_ptr, [ir.Constant(ir.IntType(32), 0), builder.load(pointer_ptr)]))])
        elif i == ",": builder.store(builder.call(getch_func, args = []), builder.gep(array_ptr, [ir.Constant(ir.IntType(32), 0), builder.load(pointer_ptr)]))
        elif i == "[":
            current = builder.append_basic_block()
            builder.branch(current)
            builder.position_at_end(current)
        elif i == "]":
            res = builder.icmp_signed("==", builder.load(builder.gep(array_ptr, [ir.Constant(ir.IntType(32), 0), builder.load(pointer_ptr)])), ir.Constant(ir.IntType(8), 0))
            next = builder.append_basic_block()
            builder.cbranch(res, next, builder.block)
            builder.position_at_end(next)
        else: ...

    builder.ret(ir.Constant(ir.IntType(32), 0))

def main(argv):
    module = ir.Module()
    main_func = ir.Function(module, ir.FunctionType(ir.IntType(32), []), "main")
    builder = ir.IRBuilder(main_func.append_basic_block("entry"))

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    module.triple = target_machine.triple

    compiler(builder, open(argv[1], "r").read())

    executable = os.path.split(os.path.splitext(argv[1])[0])[1] + (".exe" if sys.platform == "win32" else "")

    first_dir = os.getcwd()
    os.chdir(tempfile.gettempdir())

    with open("temp.llvm", "w") as file:
        file.write(str(module))

    subprocess.run(["opt", "temp.llvm", "-o", "temp.bc"], capture_output = True)
    os.remove(f"temp.llvm")
    subprocess.run(["llvm-dis", "temp.bc", "-o", "temp.llvm"])
    os.remove("temp.bc")
    subprocess.run(["llc", "-filetype=obj", "temp.llvm", "-o", "temp.o"])
    os.remove("temp.llvm")
    subprocess.run(["g++", os.path.split(__file__)[0] + "/asm/__chkstk.s", "-c", "-o", "__chkstk.o"])
    subprocess.run(["g++", "temp.o", "__chkstk.o", "-o", executable])
    os.remove("__chkstk.o")
    os.remove("temp.o")

    with open(executable, "rb") as file:
        data = file.read()

    os.remove(executable)
    os.chdir(first_dir)

    with open(executable, "wb") as file:
        file.write(data)

if __name__ == "__main__":
    sys.exit(main(sys.argv))