from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="CalculatorServer", port=6969)

API_URL = "https://api.aurora-dev.sinchlab.com/AuroraService/v1/"
API_USERNAME = "fb4b663c9ae241a58ac8239f910ca88c"
API_PASSWORD = "3a112f0cca8648378e4a2291f64a0b78"
import requests

@mcp.tool()
def put_together(a: int, b: int) -> int:
    print("Calling the 'add' function")
    """Adds two integer numbers together."""
    return a + b

@mcp.tool()
def custom_manipulation(a: int, b: int) -> int:
    print("Calling the 'adjust' function")
    first = a + 1
    second = b + 1
    return first + second


@mcp.tool()
def get_average(numbers: list[int]) -> float:
    print("Calling the 'get_average' function")
    """Returns the average of a list of numbers."""
    return sum(numbers) / len(numbers)
import os
from requests.auth import HTTPBasicAuth

@mcp.tool()
def http_get_two_params(
    suffix: str,
    param1_name: str,
    param1_value: str,
    param2_name: str,
    param2_value: str, verify_tls: bool = True):
    """
    Send a GET request to API_URL + suffix with two string query parameters.

    Args:
      - suffix: path after API_URL, e.g., "orders" or "regions/list"
      - param1_name: name of the first query parameter (string)
      - param1_value: value of the first query parameter (string)
      - param2_name: name of the second query parameter (string)
      - param2_value: value of the second query parameter (string)
      - username/password: Basic Auth credentials; if omitted, read from env:
          API_USERNAME / API_PASSWORD

    Returns:
      - Parsed JSON on success if response is JSON
      - Otherwise a dict with status/text
    """
    print("Calling the 'http_get_two_params' function")
    if not isinstance(param1_name, str) or not isinstance(param2_name, str):
        raise ValueError("param1_name and param2_name must be strings.")
    if not isinstance(param1_value, str) or not isinstance(param2_value, str):
        raise ValueError("param1_value and param2_value must be strings.")

    url = API_URL.rstrip("/") + "/" + suffix.lstrip("/")
    params = {param1_name: param1_value, param2_name: param2_value}

    # Resolve credentials: args take precedence over env vars
    user = API_USERNAME
    pwd = API_PASSWORD
    if not user or not pwd:
        raise ValueError("Missing Basic Auth credentials. Provide username/password or set API_USERNAME/API_PASSWORD env vars.")
    payload = {}
    headers = {
             'x-username': 'edmul1@on.sinch.com',
             'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
             'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
         }

    try:
        resp = requests.request("GET", url, headers=headers, data=payload, verify=bool(verify_tls))
    except requests.RequestException as e:
        return {
            "ok": False,
            "url": url,
            "params": params,
            "error": f"Request failed: {type(e).__name__}: {str(e)}",
        }

    content_type = resp.headers.get("Content-Type", "")
    result = {
        "ok": resp.ok,
        "status": resp.status_code,
        "url": resp.url,
        "params": params,
        "headers": dict(resp.headers),
    }
    if "application/json" in content_type.lower():
        try:
            result["json"] = resp.json()
        except ValueError:
            result["text"] = resp.text
    else:
        result["text"] = resp.text

    if not resp.ok and "error" not in result:
        result["error"] = f"HTTP {resp.status_code}"

    return result

if __name__ == "__main__":
    mcp.run("sse")