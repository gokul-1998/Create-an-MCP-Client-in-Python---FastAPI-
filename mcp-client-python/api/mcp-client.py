
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession,StdioServerParameters
from anthropic import Anthropic


class MCPClient:
    """
    A class to interact with the MCP (Multi-Channel Processor) API.
    """
    def __init__(self):
        self.session:Optional[ClientSession] = None
        self.exit_stack=AsyncExitStack()
        self.llm=Anthropic()
        self.tools=[]
        self.messages=[]
        # self.logger=logger

    