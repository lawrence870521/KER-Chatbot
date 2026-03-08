"""
KER API Tool Definitions and Execution
每個 tool 對應一個 KER API endpoint，由 Claude 決定何時呼叫
"""
import os
import httpx
from typing import Any

KER_API_BASE_URL = os.getenv("KER_API_BASE_URL", "https://your-company-api/ker")
KER_API_TOKEN = os.getenv("KER_API_TOKEN", "")


def _get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if KER_API_TOKEN:
        headers["Authorization"] = f"Bearer {KER_API_TOKEN}"
    return headers


async def call_ker_api(endpoint: str, params: dict = None) -> dict:
    """呼叫 KER API，endpoint 為相對路徑，params 為 query 參數"""
    url = f"{KER_API_BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params, headers=_get_headers())
        response.raise_for_status()
        return response.json()


# ─── Tool 執行函數 ────────────────────────────────────────────────────────────

async def get_ker_summary(date: str = "today") -> Any:
    """今日或指定日期的 KER 總覽"""
    return await call_ker_api("/summary", {"date": date})


async def get_equipment_oee(equipment: str, date: str = "today") -> Any:
    """查詢指定機台的 OEE（可用逗號分隔多台，例如 ToolA,ToolB）"""
    return await call_ker_api("/oee", {"equipment": equipment, "date": date})


async def get_equipment_detail(name: str, date: str = "today") -> Any:
    """查詢單台機台詳細資料（utilization、lost time、downtime reason）"""
    return await call_ker_api("/equipment", {"name": name, "date": date})


async def get_losttime_ranking(date: str = "today", top: int = 5) -> Any:
    """查詢 lost time 最多的機台排名"""
    return await call_ker_api("/losttime/top", {"date": date, "top": top})


async def get_equipment_trend(name: str, days: int = 7) -> Any:
    """查詢某台機台最近 N 天的效率趨勢"""
    return await call_ker_api(f"/equipment/trend", {"name": name, "days": days})


async def get_ker_by_date_range(start_date: str, end_date: str) -> Any:
    """查詢某段日期區間的 KER 資料"""
    return await call_ker_api("/range", {"start": start_date, "end": end_date})


# ─── Claude Tool Schema 定義 ──────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_ker_summary",
        "description": (
            "Get KER (Key Equipment Report) summary for a specific date. "
            "Returns average OEE, average utilization, total lost time, and worst-performing equipment. "
            "Use this when user asks about overall KER status or daily summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to query. Use 'today', 'yesterday', or ISO format 'YYYY-MM-DD'.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_equipment_oee",
        "description": (
            "Get OEE (Overall Equipment Effectiveness) for one or more specific equipment. "
            "Use this when user asks about OEE for specific machines or wants to compare multiple machines. "
            "Multiple equipment names should be comma-separated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equipment": {
                    "type": "string",
                    "description": "Equipment name(s). Single: 'ToolA'. Multiple: 'ToolA,ToolB,ToolC'.",
                },
                "date": {
                    "type": "string",
                    "description": "Date to query. Use 'today', 'yesterday', or ISO format 'YYYY-MM-DD'.",
                },
            },
            "required": ["equipment"],
        },
    },
    {
        "name": "get_equipment_detail",
        "description": (
            "Get detailed KER data for a single equipment, including running time, idle time, "
            "downtime, lost time, utilization rate, and downtime reason. "
            "Use this when user asks about a specific machine's performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Equipment name, e.g., 'ToolA'.",
                },
                "date": {
                    "type": "string",
                    "description": "Date to query. Use 'today', 'yesterday', or ISO format 'YYYY-MM-DD'.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_losttime_ranking",
        "description": (
            "Get ranking of equipment by lost time (highest first). "
            "Use this when user asks which equipment has the most lost time, "
            "or wants to know the worst-performing equipment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to query. Use 'today', 'yesterday', or ISO format 'YYYY-MM-DD'.",
                },
                "top": {
                    "type": "integer",
                    "description": "Number of top results to return. Default is 5.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_equipment_trend",
        "description": (
            "Get efficiency trend data for a specific equipment over the past N days. "
            "Use this when user asks about trends, recent performance history, or week-over-week changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Equipment name, e.g., 'ToolA'.",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of past days to include. Default is 7.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_ker_by_date_range",
        "description": (
            "Get KER data for a specific date range. "
            "Use this when user asks about weekly or monthly reports."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format 'YYYY-MM-DD'.",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format 'YYYY-MM-DD'.",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
]

# ─── Tool 路由 ────────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_ker_summary": get_ker_summary,
    "get_equipment_oee": get_equipment_oee,
    "get_equipment_detail": get_equipment_detail,
    "get_losttime_ranking": get_losttime_ranking,
    "get_equipment_trend": get_equipment_trend,
    "get_ker_by_date_range": get_ker_by_date_range,
}


async def execute_tool(name: str, tool_input: dict) -> str:
    """執行指定的 tool，回傳 JSON 字串給 Claude"""
    import json
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = await handler(**tool_input)
        return json.dumps(result, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"API error {e.response.status_code}: {e.response.text}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Cannot connect to KER API: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
