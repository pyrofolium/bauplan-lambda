- This is in alpha build. 

Bauplan lambda. 

A small library enabling you to code in python on the cloud. 

Before running make sure you run `aws configure` to get your local environment working on aws.

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
    from lambda_builder import LambdaBuilder
    
    lambda_env = LambdaBuilder(
        role_name="<A-ROLE-NAMe>", #must have persmissions to spawn lambda 
        lambda_function_name="<A-FUNCTION-NAME>", 
        region="A-REGION-NAME")

    @lambda_env.cloud_execute()
    def fib(n: int) -> int:
        if n < 0:
            return 0
        elif n <= 1:
            return 1
        else:
            return fib(n - 1) + fib(n - 2)

    #will spawn 9 aws lambdas in a recursive chain
    print(fib(4))
```
    
Async await syntax is supported to for concurrency. Lambdas will be running in parallel. 

```python
    from lambda_builder import LambdaBuilder
    import asyncio

    @lambda_env.aio_cloud_execute()
    async def async_fib(n: int) -> int:
        if n < 0:
            return 0
        elif n <= 1:
            return n
        else:
            result = await asyncio.gather(async_fib(n - 1), async_fib(n - 2))
            return sum(result)
```

Submit a pull request or email heynairb@gmail.com for any issues. 
    