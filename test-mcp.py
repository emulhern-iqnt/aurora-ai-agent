from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="CalculatorServer", port=6969)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two integer numbers together."""
    return a + b

    # server.py (continued)
if __name__ == "__main__":
   mcp.run("sse")