
# Instructions:

1. Make sure you're in an environment configured by the aws-cli and that the .aws folder is configured correctly. 
2. Make sure you run python 3.10 to match the lambda version
3. Read main.py to see examples and test the library. You will need to edit main.py for it to work: Read the comments in the first couple lines. 
4. You should be able to run the main.py within the project folder with "python main.py"

## Notes:
- Ultimately, the objective here was to be minimally invasive with the library and keep the UX as close as possible to developing something on a standard python project.
- The way the library is designed allows it to support a single global environment or multiple. Single is the default.
- This library is a very rough experimental prototype.
- Because it's a prototype there are many known issues with it including certain features it does not support and certain optimization issues. 
- I can discuss these issues in the followup.   
- main.py is an example 
- lambda_function.py is the handler file in the lambda.
- lambda_builder.py, and utils.py are libraries for the client side.
- The user should be able to edit files, add new functionality without the library having to spawn a new lambda function.
- The only thing that will trigger a creation of a lambda function is when the user adds a new library to the project via pip or the requirements' dictionary.
- lambda environments are built and cached locally in the "packages" folder