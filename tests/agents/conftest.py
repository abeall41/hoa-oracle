import os
import sys

# Add both agent tool directories to sys.path so tests can import tool
# implementations directly. Needed because directory names contain hyphens
# which Python's import system cannot handle as package names.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_GOVERNANCE_TOOLS = os.path.join(_ROOT, "agents", "governance-mcp", "tools")
_CS_TOOLS = os.path.join(_ROOT, "agents", "customer-service-mcp", "tools")

for path in (_ROOT, _GOVERNANCE_TOOLS, _CS_TOOLS):
    if path not in sys.path:
        sys.path.insert(0, path)
