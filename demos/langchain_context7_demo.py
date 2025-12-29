import asyncio
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
# from langchain_mcp_adapters.client import MultiServerMCPClient
from ctrl.langchain.client import CtrlMCP  # NEW


async def main():
    mcp = CtrlMCP(
        servers="configs/servers.yaml", 
        policy="configs/policy.yaml", 
        risk="configs/risk.yaml",
        db_path="ctrl.db"
        )

    tools = await mcp.get_tools()

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
    agent = create_agent(llm, tools)
    out = await agent.ainvoke(
        {
            "messages": [
                (
                    "user",
                    "Use Context7 tools. Fetch documentation for library `vercel/next.js`. "
                    "Summarize how to use create_agent with a short code example."
                )
            ]
        }
    )

    last = out["messages"][-1]

    # 1) The actual user-visible answer
    print("CONTENT:\n", last.content)

    # 2) If content is empty, inspect tool calls / structured output
    # print("\nADDITIONAL_KWARGS:\n", getattr(last, "additional_kwargs", None))

    # 3) Dump the whole trace (very useful)
    # print("\n--- FULL TRACE ---")
    # for i, m in enumerate(out["messages"]):
    #     role = getattr(m, "type", m.__class__.__name__)
    #     print(f"\n[{i}] {role}")
    #     print("content:", repr(getattr(m, "content", "")))
    #     if getattr(m, "additional_kwargs", None):
    #         print("additional_kwargs:", m.additional_kwargs)



if __name__ == "__main__":
    asyncio.run(main())
