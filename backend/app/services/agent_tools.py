import json
from sqlalchemy.orm import Session
from langchain_core.tools import tool
from datetime import datetime

from app.models.user import User
from app.services import kb_service, lab_service, equipment_service, reservation_service
from app.schemas.reservation import ReservationCreateRequest
from app.core.exceptions import BusinessException


def bulid_tools(db: Session, current_user: User):
    @tool
    def search_lab_docs(query: str):
        """查询知识库库"""
        try:
            return kb_service.search(query) or "没有找到相关资料"
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "search_lab_docs\n" + str(e)},
                ensure_ascii=False,
            )

    @tool
    def list_open_labs(keywords: str = "") -> str:
        """查询开放实验室"""
        try:
            keywords = keywords.strip() or None
            page = lab_service.get_labs_page_list(
                db, page=1, page_size=10, keywords=keywords, status=1
            )

            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location,
                    "capacity": item.capacity,
                    "open_time": item.open_time,
                    "close_time": item.close_time,
                }
                for item in page.list
            ]
            return json.dumps({"total": page.total, "labs": rows}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "list_open_labs\n" + str(e)}, ensure_ascii=False
            )

    @tool
    def list_lab_equipments(lab_id: int, keywords: str = "") -> str:
        """查询实验室设备"""
        try:
            keywords = keywords.strip() or None
            page = equipment_service.get_equipment_page_list(
                db, page=1, page_size=10, lab_id=lab_id, keywords=keywords
            )

            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "lab_id": item.lab_id,
                    "lab_name": item.lab_name,
                    "sepc": item.spec,
                    "quantity": item.quantity,
                    "status": item.status,
                }
                for item in page.list
            ]
            return json.dumps(
                {"total": page.total, "equipments": rows}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "list_lab_equipments\n" + str(e)},
                ensure_ascii=False,
            )

    @tool
    def create_lab_reservation(
        lab_id: int,
        date: str,
        start_time: str,
        end_time: str,
        equipment_id: int | None = None,
        remark: str | None = None,
    ):
        """创建实验室预约"""
        try:
            payload = ReservationCreateRequest(
                lab_id=lab_id,
                equipment_id=equipment_id,
                date=date,
                start_time=start_time,
                end_time=end_time,
                remark=remark,
            )
            reservation_service.creaet_reservation(db, current_user, payload)
            return json.dumps(
                {
                    "ok": True,
                    "message": "预约已提交，请等待管理员审核",
                    "lab_id": lab_id,
                    "equipment_id": equipment_id,
                    "date": date,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                ensure_ascii=False,
            )
        except BusinessException as e:
            return json.dumps(
                {"ok": False, "error": str(e.message)}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "create_lab_reservation\n" + str(e)},
                ensure_ascii=False,
            )

    @tool
    def get_today() -> str:
        """获取当前时间 格式YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")

    return [
        search_lab_docs,
        list_open_labs,
        list_lab_equipments,
        create_lab_reservation,
        get_today,
    ]
