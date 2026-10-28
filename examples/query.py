"""Run with the installed package: python examples/query.py. Sends public API GETs."""

import asyncio
import json

from uk_data_mcp.service import DataService
from uk_data_mcp.transport import HttpClient


async def main():
    async with HttpClient() as http:
        result = await DataService(http).call(
            "site_context",
            {
                "latitude": 52.45,
                "longitude": -1.93,
                "nation": "England",
                "radius_km": 1,
                "limit_per_source": 3,
            },
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
