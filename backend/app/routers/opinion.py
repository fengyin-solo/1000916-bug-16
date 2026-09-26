"""客户反馈接口：维护反馈记录，覆盖受理反馈、处理完成、关闭反馈等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.opinion import OpinionService

router = APIRouter(prefix="/api/opinion", tags=["客户反馈"])

service = OpinionService()

LIST_FIELDS = ["反馈编号", "委托单位", "反馈类型", "反馈内容", "处理人员", "处理结果", "反馈日期", "反馈状态"]
STATUSES = ["待受理", "处理中", "已处理", "已关闭"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按反馈编号检索"),
    client: str | None = Query(default=None, description="按委托单位检索"),
    category: str | None = Query(default=None, description="按反馈类型检索"),
    status: str | None = Query(default=None, description="待受理、处理中、已处理、已关闭"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按反馈编号、委托单位、反馈类型与状态过滤客户反馈列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"反馈状态「{status}」不在可选范围内")
    items, total = service.list_entries(
        keyword=keyword,
        client=client,
        category=category,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出客户反馈清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "opinion", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条反馈记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"反馈记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条反馈记录，缺字段时说明原因；反馈编号重复提交只生效一次。"""
    entry, missing, message = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}，请补充后重新提交")
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条反馈记录执行受理反馈、处理完成、关闭反馈；不允许的动作会被拦下并说明原因。

    处理完成需要在 values 中同时带上处理人员、处理结果；重复提交同一动作只生效一次。
    """
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
