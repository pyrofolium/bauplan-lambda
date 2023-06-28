#!/usr/bin/env python3

import json
import os.path
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict, Optional, Union, Awaitable
import base64
import lzma
import boto3
import dill as pickle
import inspect
import asyncio
from utils import build_env, get_project_reqs, hash_env, get_context_from_file, get_python_project_structure, \
    is_in_aws_lambda, find_file_with_function


class LambdaBuilder:
    def __init__(self,
                 role_name: str,
                 region: str,
                 lambda_function_name,
                 requirements: Optional[Dict[str, str]] = None,
                 runtime: str = "python3.10",
                 package_dir: str = "packages",
                 force_rebuild: bool = False,
                 mock_mode: bool = False,
                 thread_count_per_lambda: int = 8,
                 s3_bucket: Optional[str] = None,
                 s3_key: Optional[str] = None):
        self.thread_count = thread_count_per_lambda
        self.mock_mode = mock_mode
        if mock_mode:
            return
        requirements = get_project_reqs() if requirements is None else requirements
        requirements |= {"dill": "0.3.6"}
        self.package_hash = hash_env(requirements)
        self.lambda_function_name = lambda_function_name
        self.lambda_client = boto3.client("lambda", region)
        lambda_functions = self.list_lambda_functions()
        if not is_in_aws_lambda():  # no building in aws lambda, lambdas can only invoke they cannot create lambdas.
            does_lambda_exist_in_aws = self.lambda_function_name in lambda_functions
            was_package_built = os.path.exists(f"{package_dir}/{self.package_hash}")
            was_pacakge_zipped = os.path.exists(f"{package_dir}/{self.package_hash}.zip")
            should_rebuild = not was_package_built or not was_pacakge_zipped or force_rebuild or not does_lambda_exist_in_aws
            if should_rebuild and was_package_built:
                shutil.rmtree(f"{package_dir}/{self.package_hash}")
            if should_rebuild and was_pacakge_zipped:
                os.remove(f"{package_dir}/{self.package_hash}.zip")
            if self.lambda_function_name in lambda_functions and should_rebuild:
                self.lambda_client.delete_function(FunctionName=self.lambda_function_name)
            if should_rebuild:
                print("building python environment")
                build_env(self.package_hash, requirements=requirements, package_dir=package_dir)
                print("finished creating python environment")
                zip_file_path = os.path.join(f"{package_dir}", f"{self.package_hash}.zip")
                with open(zip_file_path, 'rb') as file:
                    lambda_zip_package = file.read()
                role_arn: Optional[str] = boto3.client('iam').get_role(RoleName=role_name)['Role']['Arn']
                print(f"creating function: {self.lambda_function_name}")
                code_parameter = {
                    "ZipFile": lambda_zip_package,
                    "S3Bucket": s3_bucket if s3_bucket is not None else None,
                    "S3Key": self.lambda_function_name if s3_bucket is not None else None,
                }
                code_parameter = {k: v for k, v in code_parameter.items() if v is not None}
                response = self.lambda_client.create_function(
                    FunctionName=self.lambda_function_name,
                    Description="lambda executer",
                    Runtime=runtime,
                    Handler="lambda_function.lambda_handler",
                    MemorySize=256,
                    Code=code_parameter,
                    Timeout=300,
                    Role=role_arn
                )
                waiter = self.lambda_client.get_waiter('function_active_v2')
                waiter.wait(FunctionName=self.lambda_function_name)
                print("finished creating aws function")

    def list_lambda_functions(self) -> Dict[str, Dict[str, Union[str, int, Dict]]]:
        return {i['FunctionName']: i for i in self.lambda_client.list_functions()['Functions']}

    def cloud_execute(self, local=False):
        def inner(func: Callable[[...], Any]) -> Callable[[...], Any]:
            if inspect.iscoroutinefunction(func):
                raise Exception("cloud_execute cannot decorated on async functions.")

            def result(*args, force_local: bool = False, **kwargs) -> Any:
                # once a function is invoked, that function is not called locally but is called on a lambda with an
                # identical environment. On that lambda the function will be called locally so a force_local
                # parameter is passed to the decorated function to indicate that.
                if local or self.mock_mode or force_local:
                    # del kwargs["force_local"]
                    return func(*args, **kwargs)

                else:
                    # the entire project of python files is passed to the invocation.
                    python_project_files = get_python_project_structure(os.getcwd(),
                                                                        ["venv", "__pycache__", "packages"], r"^\..*")

                    # relevant function name is passed to the lambda.
                    func_name = func.__name__

                    # The logic below is used to grab an ast tree of the file in which the function above is located.
                    # this ast tree is passed to the invocation.
                    file_path = inspect.getabsfile(func)
                    if not os.path.isdir(file_path):
                        context = get_context_from_file(file_path)
                    else:
                        file_path = f"{os.getcwd()}/{find_file_with_function(func_name, python_project_files)}"
                        if file_path is None:
                            raise Exception(f"function with name: {func_name} could not be found")
                        context = get_context_from_file(file_path)

                    # this code is the compressed data that is passed to the lambda.
                    serialized_data = base64.b85encode(
                        lzma.compress(
                            pickle.dumps(
                                (python_project_files, context, func_name, args, kwargs)
                            )
                        )
                    ).decode('utf-8')
                    response = self.lambda_client.invoke(
                        FunctionName=self.lambda_function_name,
                        Payload=json.dumps({"data": serialized_data}).encode('utf-8'),
                        InvocationType="RequestResponse"
                    )
                    return pickle.loads(
                        lzma.decompress(
                            base64.b85decode(
                                json.loads(
                                    response['Payload'].read()
                                )['data']
                            )
                        )
                    )

            return result

        return inner

    # quick and dirty async version of the above decorator.
    # mostly uses identical and copied logic.
    def aio_cloud_execute(self, local=False):
        def inner(func: Callable[[...], Awaitable[Any]]) -> Union[Callable[[...], Awaitable[Any]]]:
            if not inspect.iscoroutinefunction(func):
                raise Exception("Incorrect decoration, can only decorate async functions with aio_cloud_execute")

            async def result(*args, force_local=False, **kwargs) -> Awaitable[Any]:
                if local or self.mock_mode or force_local:
                    return await func(*args, **kwargs)
                else:
                    python_project_files = get_python_project_structure(os.getcwd(),
                                                                        ["venv", "__pycache__", "packages"], r"^\..*")
                    func_name = func.__name__
                    file_path = inspect.getabsfile(func)
                    if not os.path.isdir(file_path):
                        context = get_context_from_file(file_path)
                    else:
                        file_path = find_file_with_function(func_name, python_project_files)
                        if file_path is None:
                            raise Exception(f"function with name: {func_name} could not be found")
                        context = get_context_from_file(file_path)

                    serialized_data = base64.b85encode(
                        lzma.compress(
                            pickle.dumps(
                                (python_project_files, context, func_name, args, kwargs)
                            )
                        )
                    ).decode('utf-8')

                    invoke_params = {
                        "FunctionName": self.lambda_function_name,
                        "Payload": json.dumps({"data": serialized_data}).encode('utf-8'),
                        "InvocationType": "RequestResponse"
                    }
                    invokation_function = lambda _: self.lambda_client.invoke(**invoke_params)
                    response = await asyncio.get_event_loop() \
                        .run_in_executor(ThreadPoolExecutor(max_workers=self.thread_count), invokation_function, None)
                    return pickle.loads(
                        lzma.decompress(
                            base64.b85decode(
                                json.loads(
                                    response['Payload'].read()
                                )['data']
                            )
                        )
                    )

            return result

        return inner
