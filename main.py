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

    pointer, pos, start = 0, 0, []
    array = [0]

    while len(content) > pos:
        if content[pos] == "<": pointer -= 1
        elif content[pos] == ">": pointer += 1
        elif content[pos] == "+": array[pointer] += 1
        elif content[pos] == "-": array[pointer] -= 1
        elif content[pos] == ".": builder.call(printf_func, args = [create_string(builder, "%c"),
                                                                    ir.Constant(ir.IntType(8), array[pointer]) if isinstance(array[pointer], int) else array[pointer]])
        elif content[pos] == ",": array[pointer] = builder.call(getch_func, args = [])
        elif content[pos] == "[": start.append(pos)
        elif content[pos] == "]":
            if array[pointer] > 0: pos = start[len(start) - 1] - 1
            else: start.pop(len(start) - 1)
        else: ...
        if pointer > len(array) - 1: array.append(0)
        pos += 1

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
    subprocess.run(["g++", "temp.o", "-o", executable])
    os.remove("temp.o")

    with open(executable, "rb") as file:
        data = file.read()

    os.remove(executable)
    os.chdir(first_dir)

    with open(executable, "wb") as file:
        file.write(data)

if __name__ == "__main__":
    sys.exit(main(sys.argv))