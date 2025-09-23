from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="CalculatorServer", port=6969)

API_URL = "https://api.aurora-dev.sinchlab.com/AuroraService/v1/"
API_USERNAME = "fb4b663c9ae241a58ac8239f910ca88c"
API_PASSWORD = "3a112f0cca8648378e4a2291f64a0b78"

import os
from requests.auth import HTTPBasicAuth
import requests
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode  # added

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

# @mcp.tool()
# def http_get_two_params(
#     suffix: str,
#     param1_name: str,
#     param1_value: str,
#     param2_name: str,
#     param2_value: str):
#     """
#     Send a GET request to API_URL + suffix with two string query parameters.
#
#     Args:
#       - suffix: path after API_URL, e.g., "orders" or "regions/list"
#       - param1_name: name of the first query parameter (string)
#       - param1_value: value of the first query parameter (string)
#       - param2_name: name of the second query parameter (string)
#       - param2_value: value of the second query parameter (string)
#       - username/password: Basic Auth credentials; if omitted, read from env:
#           API_USERNAME / API_PASSWORD
#
#     Returns:
#       - Parsed JSON on success if response is JSON
#       - Otherwise a dict with status/text
#     """
#     print("Calling the 'http_get_two_params' function")
#     if not isinstance(param1_name, str) or not isinstance(param2_name, str):
#         raise ValueError("param1_name and param2_name must be strings.")
#     if not isinstance(param1_value, str) or not isinstance(param2_value, str):
#         raise ValueError("param1_value and param2_value must be strings.")
#
#     url = API_URL.rstrip("/") + "/" + suffix.lstrip("/")
#     params = {param1_name: param1_value, param2_name: param2_value}
#
#     # Resolve credentials: args take precedence over env vars
#     user = API_USERNAME
#     pwd = API_PASSWORD
#     if not user or not pwd:
#         raise ValueError("Missing Basic Auth credentials. Provide username/password or set API_USERNAME/API_PASSWORD env vars.")
#     payload = {}
#     headers = {
#              'x-username': 'edmul1@on.sinch.com',
#              'Authorization': 'Basic ZmI0YjY2M2M5YWUyNDFhNThhYzgyMzlmOTEwY2E4OGM6M2ExMTJmMGNjYTg2NDgzNzhlNGEyMjkxZjY0YTBiNzg=',
#              'Cookie': 'JSESSIONID=DCC3B6C89D58E18F6EA692202C234C52'
#          }
#
#     try:
#         resp = requests.request("GET", url, headers=headers, data=payload)
#     except requests.RequestException as e:
#         return {
#             "ok": False,
#             "url": url,
#             "params": params,
#             "error": f"Request failed: {type(e).__name__}: {str(e)}",
#         }
#
#     content_type = resp.headers.get("Content-Type", "")
#     result = {
#         "ok": resp.ok,
#         "status": resp.status_code,
#         "url": resp.url,
#         "params": params,
#         "headers": dict(resp.headers),
#     }
#     if "application/json" in content_type.lower():
#         try:
#             result["json"] = resp.json()
#         except ValueError:
#             result["text"] = resp.text
#     else:
#         result["text"] = resp.text
#
#     if not resp.ok and "error" not in result:
#         result["error"] = f"HTTP {resp.status_code}"
#
#     return result
@mcp.tool()
def create_http_request(
    suffix: str,
    param1_name: str | None = None,
    param1_value: str | None = None,
    param2_name: str | None = None,
    param2_value: str | None = None,
):
    print("Calling the 'create_http_request' function")

    from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

    def _is_blank(x):
        return x is None or (isinstance(x, str) and x.strip() == "")

    base = API_URL.rstrip("/")
    suff = suffix.lstrip("/")
    raw_url = f"{base}/{suff}"

    # If no parameters are supplied (all missing/blank), return URL without any query string
    if all(_is_blank(v) for v in (param1_name, param1_value, param2_name, param2_value)):
        return raw_url

    # Parse any existing query in suffix and merge only complete name/value pairs
    parsed = urlparse(raw_url)
    existing_qs = dict(parse_qsl(parsed.query, keep_blank_values=True))

    new_params = {}
    if not _is_blank(param1_name) and not _is_blank(param1_value):
        new_params[param1_name] = param1_value
    if not _is_blank(param2_name) and not _is_blank(param2_value):
        new_params[param2_name] = param2_value

    # If no valid pairs provided, return the base URL without adding defaults
    if not new_params:
        return raw_url

    merged_params = {**existing_qs, **new_params}
    new_query = urlencode(merged_params, doseq=True)
    url = urlunparse(parsed._replace(query=new_query))
    return url


if __name__ == "__main__":
    mcp.run("sse")