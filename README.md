- This is in alpha build. 

# Bauplan lambda. 

### A small library enabling you to code in python on the cloud. This library decorates functions such that functions are executed on aws lambdas. Each call whether on your local machine or on a aws lambda will invoke and execute on a lambda. 

#### Quickstart:

Before running make sure you run `aws configure` to get your local environment working on aws.

The library uses boto3 which requires the above command to create a .aws folder with credentials inside to work seemlessly. 

You can install aws-cli with several package managers:

MacOS/Linux:

`brew install aws-cli`

Other Linux:

`curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install`

See here for more details on installing `aws-cli`: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html


Example code:

```python
from bauplan.lambda_builder import LambdaBuilder

lambda_env = LambdaBuilder(
    role_name="<A-ROLE-NAME>",  # must have persmissions to spawn lambda 
    lambda_function_name="<A-FUNCTION-NAME>",
    region="<A-REGION-NAME>",
    runtime="python3.10")


@lambda_env.cloud_execute()
def fib(n: int) -> int:
    if n < 0:
        return 0
    elif n <= 1:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


# will spawn 9 aws lambdas in a recursive chain
print(fib(4))
```
    
Async await syntax is supported as well for concurrency. Lambdas will be running in parallel.

```python
from bauplan.lambda_builder import LambdaBuilder
import asyncio


@lambda_env.aio_cloud_execute()
async def async_fib(n: int) -> int:
    if n < 0:
        return 0
    elif n <= 1:
        return 1
    else:
        result = await asyncio.gather(async_fib(n - 1), async_fib(n - 2))
        return sum(result)

asyncio.run(async_fib(4))
```

Submit a pull request or email heynairb@gmail.com for any issues. 
    
