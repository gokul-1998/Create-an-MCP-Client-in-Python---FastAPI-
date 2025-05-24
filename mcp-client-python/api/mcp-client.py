
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession,StdioServerParameters
from anthropic import Anthropic
from mcp.client.stdio import stdio_client
import traceback

from utils import logger
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
        self.logger=logger

    # connect to MCP server
    async def connect_to_server(self,server_script_path:str):
        try:
            is_python=server_script_path.endswith(".py")
            is_js=server_script_path.endswith(".js")
            if not (is_python or is_js):
                raise ValueError("Server script must be a .py or .js file")
            
            command = "python" if is_python else "node"
            server_params=StdioServerParameters(
                command=command,
                args=[server_script_path],
                env=None,
                
            )

            stdio_transport=await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio,self.write=stdio_transport
            self.session=await self.exit_stack.enter_async_context(ClientSession(self.stdio,self.write))


            await self.session.initialize()

            self.logger.info("Connected to MCP server")

            mcp_tools=await self.get_mcp_tools()
            self.tools=[
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool.input_schema,
                }
                for tool in mcp_tools
            ]
            self.logger.info(f" available Tools: {self.tools}")

        except Exception as e:
            self.logger.error(f"Error connecting to server: {e}")
            traceback.print_exc()
            print(f"Error connecting to server: {e}")
            raise e


# get mcp tool list
    async def get_mcp_tools(self):
        try:
            response = await self.session.list_tools()
            return response["tools"]
        except Exception as e:
            self.logger.error(f"Error getting MCP tools: {e}")
            traceback.print_exc()
            print(f"Error getting MCP tools: {e}")
            raise e
        

    # cleanup
    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
            self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()
            print(f"Error during cleanup: {e}")
            raise e
        
    # process query
    async def process_query(self,query:str):
        try:
            self.logger.info(f"Processing query: {query}")
            user_message={
                "role":"user",
                "content":query
            }
            self.messages=[user_message]
            while True:
                response=await self.call_llm()

                # the response is a text message
                if response.content[0].type =="text" and len(response.content) == 1:
                   assistant_message={
                        "role":"assistant",
                        "content":response.content[0].text
                    }
                   self.messages.append(assistant_message)
                #    await self.log_conversation(self.messages)
                   self.messages.append(assistant_message)
                   break


            # the response is a tool call
                assistant_message={
                    "role":"assistant",
                    "content":response.to_dict()['content']
                }
                self.messages.append(assistant_message)

                for content in response.content:
                    if content.type == "text":
                        self.logger.info(f"Text response: {content.text}")
                        self.messages.append({
                            "role": "assistant",
                            "content": content.text
                        }) 
                    elif content.type == "tool_call":
                        tool_name=content.name
                        tool_args=content.input
                        tool_use_id=content.id
                        self.logger.info(f"Tool call: {tool_name} with args {tool_args} and id {tool_use_id}")
                        try:
                            result=await self.session.call_tool(tool_name, tool_args)
                            self.logger.info(f"Tool {tool_name} result: {result[:100]}...")
                            self.messages.append({
                                "role":"user",
                                "content":[
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content":result.content
                                    }
                                ]
                            })
                        
                        except Exception as e:
                            self.logger.error(f"Error calling tool {tool_name}: {e}")
                            traceback.print_exc()
                            print(f"Error calling tool {tool_name}: {e}")
                            raise e
            return result

        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            traceback.print_exc()
            print(f"Error processing query: {e}")
            raise e
        

    # call llm
    async def call_llm(self):
        try:
            self.logger.info("calling LLM")
            return await self.llm.messages.create(
                model="claude-2",
                max_tokens=1000,
                messages=self.messages,
                tools=self.tools
              
            )
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            traceback.print_exc()
            print(f"Error calling LLM: {e}")
            raise e