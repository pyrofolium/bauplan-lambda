import asyncio
import inspect
import os
import shutil
import lzma
import dill as pickle
from typing import Union, Dict
import base64
import sys


def delete_all_in_directory(directory: str) -> None:
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # remove file or symbolic link
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # remove directory
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')


def write_file(path: str, data: bytes) -> None:
    with open(path, 'wb') as file:
        file.write(data)


FileStructure = Dict[str, Union[bytes, 'FileStructure']]


def write_python_file_structure(path: str, file_structure: FileStructure) -> None:
    for name, value in file_structure.items():
        if isinstance(value, bytes):
            write_file(os.path.join(path, name), value)
        elif isinstance(value, Dict):
            write_python_file_structure(os.path.join(path, name), value)
        else:
            raise Exception("Logic error with write_python_file_structure")


def function(data: bytes) -> Dict[str, bytes]:
    project_files, context, func_name, args, kwargs = pickle.loads(
        lzma.decompress(base64.b85decode(data)))
    write_python_file_structure(os.getcwd(), project_files)
    locals_copy = {"__name__": "LambdaExecutor"}

    # ast of a file relevant to the function being called is compiled and executed so that
    # this changes the state of the program so it's in the right context such that I can grab the function.
    code = compile(context, filename="", mode="exec")
    exec(code, locals_copy, locals_copy)
    locals().update(locals_copy)
    func = locals()[func_name]

    if inspect.iscoroutinefunction(func):
        data = asyncio.run(func(*args, force_local=True, **kwargs))
    else:
        data = func(*args, force_local=True, **kwargs)
    return {"data": base64.b85encode(lzma.compress(pickle.dumps(data)))}


# /tmp dir can be written to, I change context to this dir, and have python search in this directory for imports.
def lambda_handler(event, context, dir: str = "/tmp"):
    delete_all_in_directory(dir)
    os.chdir(dir)
    sys.path.append(os.getcwd())
    return function(event["data"])

# below is for debug purposes. This file is executed on a lambda, I can simulate the execution locally by grabbing
# the serialized data and pasting it below to test you must uncomment the below find the is_in_aws() function and
# run it. you can find the serialized data by setting break points on the request object before invocation. copy and
# paste it here.

# if __name__ == "__main__":
#   event = { "data": <placed serialized_data here> }
#   os.mkdir(".scratch")
#   print(lambda_handler(event, {}, ".scratch"))
