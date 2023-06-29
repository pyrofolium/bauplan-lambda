import ast
import hashlib
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
import zipfile
from typing import List, Union, Optional, Dict, Set
import re


# for optimization these functions should be rewritten in C, C++ or Rust.
# and accessed via ffi from python. All of this puts initialization overhead
# on the lambda and any optimization that reduces that makes the experience
# more invisible to the user.

# for functions that access the filesystem a further optimization should be an
# in memory virtual filesystem so the actual filesystem is never touched for
# a pretty good speed up here.

def get_context_from_file(path: str) -> ast.Module:
    current_file_path = os.path.realpath(path)
    with open(current_file_path, 'r') as f:
        file_content = f.read()
        root_nodes = ast.parse(file_content)
        return root_nodes


@contextmanager
def change_directory(destination: str) -> None:
    try:
        cwd = os.getcwd()
        os.chdir(destination)
        yield
    finally:
        os.chdir(cwd)


@contextmanager
def failure_tracker() -> None:
    try:
        did_previous_build_fail = False
        if os.path.exists("fail"):
            did_previous_build_fail = True
        else:
            with open("fail", "w"):
                pass
        yield did_previous_build_fail
    except Exception as e:
        raise Exception(e)
    os.remove("fail")


Requirements = Dict[str, str]


def build_env(package_hash: str, requirements: Requirements, package_dir="packages") -> str:
    if not os.path.exists(package_dir):
        os.mkdir(package_dir)
    with change_directory(package_dir):
        package_does_not_exist = False
        archive_does_not_exist = False
        if not os.path.exists(package_hash):
            package_does_not_exist = True
            os.mkdir(package_hash)
        if not os.path.exists(f"{package_hash}.zip"):
            archive_does_not_exist = True
        with change_directory(package_hash):
            with failure_tracker() as did_previous_build_fail:
                if did_previous_build_fail or package_does_not_exist:
                    [install_package(package, version) for package, version in requirements.items()]
                    with change_directory("../"):
                        with change_directory("../"):
                            filename = "lambda_function.py"
                            pathname = os.path.join("src/bauplan", filename)
                            shutil.copy2(pathname, os.path.join(f"{package_dir}/{package_hash}", filename))
                if did_previous_build_fail or archive_does_not_exist or package_does_not_exist:
                    with change_directory("../"):
                        zip_directory(f"./{package_hash}", f"{package_hash}.zip")
    return package_hash


def get_project_reqs() -> Dict[str, str]:
    command = [sys.executable, "-m", "pip", "freeze"]
    output_str = subprocess.check_output(command).decode('utf-8')
    parsed_reqs = [[j.strip() for j in i.split("==")] for i in output_str.split("\n")[:-1]]
    return {key: value for key, value in parsed_reqs}


def hash_env(requirements: Requirements) -> str:
    x = [str((k, v)) for k, v in requirements.items()]
    x.sort()
    sha_signature = hashlib.sha256("".join(x).encode()).hexdigest()
    return sha_signature


def install_package(package_name: str, version: str) -> None:
    command = [sys.executable, "-m", "pip", "install", "--target", f"./", f"{package_name}=={version}"]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in iter(p.stdout.readline, b''):
        pass
    #     # print(line.decode('utf-8'))
    p.stdout.close()
    p.wait()


def zip_directory(directory_path: str, output_path: str) -> None:
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory_path)
                zipf.write(file_path, arcname)


def get_file(path: str) -> bytes:
    with open(path, 'rb') as file:
        return file.read()


def write_file(path: str, data: bytes) -> None:
    with open(path, 'wb') as file:
        file.write(data)


FileStructure = Dict[str, Union[bytes, 'FileStructure']]


def get_python_project_structure(path: str, excluded_file_names: Union[List[str], Set[str]],
                                 exclude_reg_exp: str) -> FileStructure:
    excluded_file_names = set(excluded_file_names)
    acc = {}
    relevant_files = [filename for filename in os.listdir(path) if
                      (os.path.isdir(os.path.join(path, filename)) or
                       filename[-3:] == ".py") and
                      filename not in excluded_file_names and
                      re.match(exclude_reg_exp, filename) is None]
    for filename in relevant_files:
        full_path = os.path.join(path, filename)
        if os.path.isdir(os.path.join(path, filename)):
            acc[filename] = get_python_project_structure(full_path, excluded_file_names, exclude_reg_exp)
        else:
            acc[filename] = get_file(full_path)
    return acc


def is_function_in_file(file_bytes: bytes, func_name: str) -> bool:
    tree = ast.parse(file_bytes.decode('utf-8'))
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)) and node.name == func_name:
            return True
    return False


def find_file_with_function(func_name: str, file_structure: FileStructure) -> Optional[str]:
    files = {name: file_bytes for name, file_bytes in file_structure.items() if isinstance(file_structure[name], bytes)}
    for name, file_bytes in files.items():
        if is_function_in_file(file_bytes, func_name):
            return name
    folders = {name: sub_structure for name, sub_structure in file_structure.items() if isinstance(sub_structure, Dict)}
    for name, sub_structure in folders.items():
        result = find_file_with_function(func_name, sub_structure)
        if result is not None:
            return f"{name}/{result}"
    return None


def write_python_file_structure(path: str, file_structure: FileStructure) -> None:
    for name, value in file_structure.items():
        if isinstance(value, bytes):
            write_file(os.path.join(path, name), value)
        elif isinstance(value, Dict):
            folder = os.path.join(path, name)
            os.mkdir(folder)
            write_python_file_structure(folder, value)
        else:
            raise Exception("Logic error with write_python_file_structure")


def is_in_aws_lambda() -> bool:
    return "AWS_LAMBDA_FUNCTION_NAME" in os.environ
    # return True #(for mocking)
