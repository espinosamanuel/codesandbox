# codesandbox
A docker sandbox to run code safely and fast.

# Python Code Execution Sandbox via API

This project provides a web service that allows users to execute arbitrary Python code in an isolated Docker container. It uses Flask to expose an API endpoint that accepts Python code, runs it, and returns the result. Each user is assigned a unique, temporary Docker container to maintain a persistent state and workspace for a limited time.

## Features

*   **Isolated Execution**: Code is run inside a secure Docker container (`python:3.13-alpine`).
*   **Stateful Sessions**: Each `user_id` is mapped to a container, allowing for state to be maintained between API calls (e.g., created files are preserved).
*   **Automatic Cleanup**: Inactive containers are automatically destroyed after a configurable timeout period to conserve resources.
*   **Data Injection**: Pass JSON data into the execution environment, which becomes available as Python variables.
*   **Workspace Inspection**: The API response includes a list of files in the container's workspace.

## Prerequisites

Before you begin, ensure you have the following installed on your system:
*   **Docker**: The Docker daemon must be running. You can find installation instructions on the [official Docker website](https://docs.docker.com/get-docker/).
*   **Python 3.8+**: The application is written in Python.
*   **Flask**: The only Python dependency for this project.

## Setup and Installation

1.  **Clone the Repository**
    ```bash
    git clone 
    cd 
    ```

2.  **Install Dependencies**
    This project uses Flask. Install it using `pip`.
    ```bash
    pip install Flask
    ```

3.  **Pull the Docker Image**
    The application uses the `python:3.13-alpine` image. Pull it from Docker Hub to speed up the first container creation.
    ```bash
    docker pull python:3.13-alpine
    ```

## Running the Application

Once the setup is complete, you can start the Flask server.

```bash
python app.py
```
By default, the application will run on `http://127.0.0.1:5000`. You will see log messages in your terminal indicating that the server and the cleanup thread have started.

## API Endpoint

The service has a single endpoint for executing code.

### `/run`

*   **Method**: `POST`
*   **Description**: Executes a snippet of Python code for a given user. If it's the user's first request, a new Docker container is created. Otherwise, the existing container for that user is reused.
*   **Content-Type**: `application/json`

#### Request Body

| Key       | Type   | Required | Description                                                                                                                   |
| :-------- | :----- | :------- | :---------------------------------------------------------------------------------------------------------------------------- |
| `user_id` | String | Yes      | A unique identifier for the user. This determines which container session to use.                                             |
| `code`    | String | Yes      | The Python code to execute. The result of the execution should be stored in a variable named `result`.                        |
| `data`    | Object | No       | A JSON object where keys are variable names and values are the data to be injected into the code's scope. Defaults to empty. |

#### Example Payload

Here is a sample JSON payload to send to the `/run` endpoint.

```json
{
    "user_id": "anonymous",
    "code": "result = x + y",
    "data": {
        "x": 1,
        "y": 2
    }
}
```

## Example Usage

You can use a tool like `curl` to interact with the API.

#### Request

```bash
curl -X POST http://127.0.0.1:5000/run -H "Content-Type: application/json" -d "{\"user_id\": \"anonymous\",\"code\": \"result = x + y\",\"data\": {\"x\": 1,\"y\": 2} }"
```

#### Successful Response

If the code runs successfully, you will receive a JSON response containing the result and a list of files in the workspace.

```json
{
  "result": 3,
  "workspace_files": [
    "total 0"
  ]
}
```

#### Error Response

If there is an error during execution (e.g., syntax error in the code), the response will include an `error` field.

```json
{
  "error": "Error running code: ...",
  "result": null,
  "workspace_files": [
    "total 0"
  ]
}
```
