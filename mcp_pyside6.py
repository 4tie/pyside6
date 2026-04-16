import subprocess
import os
from fastmcp import FastMCP

mcp = FastMCP("PySide6")

@mcp.tool()
def run_app():
    subprocess.Popen(["python", "main.py"])
    return "App launched"

@mcp.tool()
def run_tests():
    result = subprocess.run(["pytest"], capture_output=True, text=True)
    return result.stdout + result.stderr

@mcp.tool()
def read_logs():
    if os.path.exists("logs/app.log"):
        return open("logs/app.log", "r", encoding="utf8").read()
    return "No log file"

@mcp.tool()
def list_ui():
    files = []
    for root, dirs, names in os.walk("."):
        for n in names:
            if n.endswith(".ui") or n.endswith(".py"):
                files.append(os.path.join(root, n))
    return files

if __name__ == "__main__":
    mcp.run()
