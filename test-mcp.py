from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="CalculatorServer", port=6969)

@mcp.tool()
def add(a: int, b: int) -> int:
    print("Calling the 'add' function")
    """Adds two integer numbers together."""
    return a + b

@mcp.tool()
def adjust(a: int, b: int) -> int:
    print("Calling the 'adjust' function")
    first = a + 1
    second = b + 1
    return first + second

    # server.py (continued)
if __name__ == "__main__":
   mcp.run("sse")