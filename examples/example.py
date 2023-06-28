import asyncio

from lambda_builder import LambdaBuilder
import dill as pickle
from examples.other import return_two

# See constructor for options.
# User creates multiple environments by instantiating this class.
# requirements default to current environment
# you will need to change the role to something you have in your aws
# make sure aws role can invoke lambdas, you will be creating a lambda that can invoke lambdas.
# make sure you're running python 3.10!

lambda_env = LambdaBuilder(role_name="brian", lambda_function_name="brian", region="us-west-1")
# example with custom libraries.
lambda_env2 = LambdaBuilder(role_name="brian", lambda_function_name="brian2", region="us-west-1",
                            requirements={"numpy": "1.25.0"})


@lambda_env2.cloud_execute()
def test_second_environment() -> int:
    return 9


# have first environment call function in 2nd environment
@lambda_env.cloud_execute()
def first_environment_calling_another_lambda_in_another_environment() -> int:
    return test_second_environment() + 9


def external_function() -> int:
    return 1


# demonstrates lambda function accessing library primitives without local import and accessing an external function.
@lambda_env.cloud_execute()
def add(x: int, y: int) -> int:
    return pickle.loads(pickle.dumps(x + y + external_function()))

# demonstrates lambda accessing function imported in from a python file.
@lambda_env.cloud_execute()
def call_function_from_other_file():
    return return_two()


#  testing async execution (see how this is called in main):
@lambda_env.aio_cloud_execute()
async def async_add(x: int, y: int) -> int:
    return pickle.loads(pickle.dumps(x + y + external_function()))


# demonstrates tree recursion, and lambda chaining (each recursive call should spawn another lambda instance).
# DFS binary tree traversal.
# be careful (2^N) lambdas are spawned serially.
@lambda_env.cloud_execute()
def fib(n: int) -> int:
    if n < 0:
        return 0
    elif n <= 1:
        return n
    else:
        return fib(n - 1) + fib(n - 2)


# demonstrates binary tree recursion, with parallel traversal down each path via lambdas.
# be careful... roughly (2^N) lambdas are spawned quickly in increasingly parallel groups starting with
# 1 -> 2 -> 4 -> 8 ...
# a very inefficient way to do fib, but it validates lambdas working async and chaining.
@lambda_env.aio_cloud_execute()
async def async_fib(n: int) -> int:
    if n < 0:
        return 0
    elif n <= 1:
        return n
    else:
        result = await asyncio.gather(async_fib(n - 1), async_fib(n - 2))
        return sum(result)


def main():
    # should return 2
    print(call_function_from_other_file())
    # should print 2, fib(3) = fib(2) + fib(1) = fib(2) + 1 = fin(1) + fib(0) + 1 = 1 + 0 + 1 = 2
    print(fib(3))
    # should print 4, (1 + 2 + external_function())
    print(add(1, 2))
    # should print 9
    print(test_second_environment())
    # should print 18
    print(first_environment_calling_another_lambda_in_another_environment())


async def async_main():
    N = 2
    results = await asyncio.gather(*[async_add(1, 2) for _ in range(N)])
    total = sum(results)
    print(total)  # If N = 2 should print 8, (1 + 2 + external_function())*2

    fib_results = await async_fib(3)
    print(fib_results)  # should print 2


if __name__ == "__main__":
    main()
    asyncio.run(async_main())
