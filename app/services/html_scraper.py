import json
import aiohttp
from utils.logger import setup_logger
import os


STATE = os.getenv("STATE")
logger = setup_logger("scraper")


async def fetch_company_details(url: str) -> dict:
    try:
        entity_id = url.rsplit("/", 1)[-1]
        headers = {
            'Content-Type': 'application/json;charset=utf-8'
        }
        payload = {"SearchID": f"{entity_id}"}
        base_url = url.rsplit("/", 1)[0]
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(base_url, json=payload) as response:
                response.raise_for_status()
                logger.debug(f"response text for  '{url}': {await response.text()}")
                data = json.loads(await response.text())
                return await parse_html_details(data)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return {}
async def fetch_company_data(query: str) -> list[dict]:
    try:
        url = "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities"
        payload = {
            "searchValue": query,
            "searchByTypeIndicator": "EntityName",
            "searchExpressionIndicator": "BeginsWith",
            "entityStatusIndicator": "AllStatuses",
            "entityTypeIndicator":
                [
                    "Corporation",
                    "LimitedLiabilityCompany",
                    "LimitedPartnership",
                    "LimitedLiabilityPartnership"
                ],
            "listPaginationInfo":
                {
                    "listStartRecord": 1,
                    "listEndRecord": 50
                }
        }
        headers = {
            'Content-Type': 'application/json;charset=utf-8'
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = json.loads(await response.text())
                return await parse_html_search(data)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []


async def parse_html_search(data: dict) -> list[dict]:
    results = []

    # Проверка успешного ответа
    if data.get("requestStatus") != "Success":
        return results

    entities = data.get("entitySearchResultList", [])
    for entity in entities:
        results.append({
            "state": STATE,
            "name": entity.get("entityName"),
            "status": entity.get("entityStatus"),
            "id": entity.get("dosID"),
            "url": "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetEntityRecordByID/"+entity.get("dosID")
        })

    return results

async def parse_html_name_agent(data: dict) -> dict:
    for entity_id, data_row in data["rows"].items():
        entity_name = data_row.get("TITLE", [""])[0]  # берём первую строку из TITLE
        agent = data_row.get("AGENT", "")
        record_num = data_row.get("RECORD_NUM", "")
        return {
            "record_num": record_num,
            "id": entity_id,
            "name": entity_name,
            "agent": agent
        }



async def parse_html_details(data: dict) -> dict:
    def format_address(address: dict) -> str:
        try:
            parts = [
                address.get("streetAddress"),
                address.get("city"),
                address.get("state"),
                address.get("zipCode"),
                address.get("country")
            ]
            return ", ".join(filter(None, map(str.strip, parts)))
        except Exception as e:
            logger.error(f"Error formatting details: {e}")
            return ""

    entity_info = data.get("entityGeneralInfo", {})
    ceo_info = data.get("ceo", {})
    po_exec_address = data.get("poExecAddress", {})
    sop_info = data.get("sopAddress", {})
    registered_agent = data.get("registeredAgent", {})

    result = {
        "state": STATE,
        "name": entity_info.get("entityName"),
        "status": entity_info.get("entityStatus"),
        "registration_number": entity_info.get("dosID"),
        "date_registered": entity_info.get("dateOfInitialDosFiling")[:10] if entity_info.get("dateOfInitialDosFiling") else None,
        "inactive_date": entity_info.get("inactiveDate")[:10] if entity_info.get("inactiveDate") else None,
        "entity_type": entity_info.get("entityType"),
        "principal_address": format_address(po_exec_address.get("address", {})),
        "ceo_name": ceo_info.get("name"),
        "ceo_address": format_address(ceo_info.get("address", {})),
        "sop_name": sop_info.get("name"), #Service of Process on the Secretary of State as Agent
        "sop_address": format_address(sop_info.get("address", {})),
        "agent_name": registered_agent.get("name") or None,
        "agent_address": format_address(registered_agent.get("address", {})) or None,
        "document_images": []
    }

    return result