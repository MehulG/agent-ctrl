import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from ctrl.langchain.client import CtrlMCP

from pathlib import Path

BASE = Path(__file__).parent


PROMPT = """
You have access to two MCP servers and their tools:

1) coingecko  
   - Read-only crypto market data.

2) edgeone  
   - Deploys a PUBLIC HTML page and returns a URL.

IMPORTANT RULES:
- You MUST call at least TWO tools.
- You MUST call one tool from coingecko first.
- You MUST then call one tool from edgeone.
- Do NOT ask clarifying questions.
- Do NOT stop early.
- If you cannot find an edgeone tool to deploy HTML, reply exactly with:
  EDGEONE_TOOL_NOT_FOUND

TASK (follow exactly):

Step 1 — Data:
- Use a coingecko tool to fetch the top 10 cryptocurrencies by market cap in USD.
- Include: name, symbol, current price, and 24h price change percentage.

Step 2 — HTML generation:
- Generate a complete HTML document.
- Use this exact structure:
  - <title>: "Top 10 Cryptocurrencies"
  - <h1>: "Top 10 Cryptocurrencies by Market Cap"
  - A <table> with columns:
    Name | Symbol | Price (USD) | 24h Change (%)
- Inline CSS is allowed.
- JavaScript and <script> tags are NOT allowed.

Step 3 — Publish:
- Call the edgeone tool that deploys HTML.
- Pass the generated HTML as the tool argument.
- Capture the returned public URL.

Step 4 — Final response:
- Return ONLY:
  - The public URL from edgeone
  - Exactly 3 bullet-point insights based on the data

"""


async def main():

    mcp = CtrlMCP(
        servers=str(BASE / "configs/servers.yaml"),
        policy=str(BASE / "configs/policy.yaml"),
        risk=str(BASE / "configs/risks.yaml"),
        db_path="ctrl.db",
)

    tools = await mcp.get_tools()
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
    agent = create_agent(llm, tools)

    out = await agent.ainvoke({"messages": [("user", PROMPT)]})
    last = out["messages"][-1]
    print(last.content)

if __name__ == "__main__":
    asyncio.run(main())
