"""客户反馈业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "opinion"
REQUIRED_FIELDS = ["反馈编号", "委托单位", "反馈类型"]
STATUS_ORDER = ["待受理", "处理中", "已处理", "已关闭"]
ACTION_TARGETS = {"受理反馈": "处理中", "处理完成": "已处理", "关闭反馈": "已关闭"}
# 只允许沿状态序列向前流转；重复提交同一个动作按幂等处理，只生效一次。
ACTION_NEXT_INDEX = {"受理反馈": 1, "处理完成": 2, "关闭反馈": 3}


def present(entry: dict[str, Any]) -> dict[str, Any]:
    """对外展示口径：列表、详情与动作回包都走这里，保证三处看到的结论一致。"""
    data = dict(entry)
    status = str(entry.get("status") or STATUS_ORDER[0])
    data["反馈状态"] = status
    data["处理结果"] = entry.get("处理结果") if str(entry.get("处理结果") or "").strip() else None
    return data


class OpinionService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("反馈编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        feedback_no = str(values.get("反馈编号") or "").strip()
        rows = store.rows(MODULE)
        if any(str(row.get("反馈编号") or "").strip() == feedback_no for row in rows):
            return None, f"反馈编号 {feedback_no} 已存在，重复登记只生效一次"
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("反馈内容", "处理人员", "反馈日期"):
            entry[field] = values.get(field)
        entry["处理结果"] = None
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return present(entry), ""

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], str, bool]:
        """执行状态动作，返回 (回包数据, 说明, 是否成功)。

        重复提交同一个动作时不再改动记录，直接回当前结论，保证网络重试不会产生副作用。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return {}, f"反馈记录 {entry_id} 不存在或已归档", False
        if action not in ACTION_TARGETS:
            return present(entry), f"动作「{action}」不属于客户反馈可执行范围", False

        target_index = ACTION_NEXT_INDEX[action]
        current_index = STATUS_ORDER.index(entry["status"]) if entry.get("status") in STATUS_ORDER else 0
        if current_index > target_index:
            return present(entry), (
                f"反馈当前为「{entry['status']}」，不能再执行{action}，请刷新列表确认最新状态"
            ), False
        if current_index == target_index:
            # 幂等：同一条反馈编号的同一动作重复提交只生效一次。
            return present(entry), f"该反馈已{action}，请勿重复提交，处理结论保持不变", True

        if action == "处理完成":
            result = str((values or {}).get("处理结果") or "").strip()
            if not result:
                return present(entry), "处理结果不能为空，请填写本次反馈的处理结论后再提交", False
            entry["处理结果"] = result
            handler = str((values or {}).get("处理人员") or "").strip()
            if handler:
                entry["处理人员"] = handler

        entry["status"] = STATUS_ORDER[target_index]
        entry["pending"] = target_index < len(STATUS_ORDER) - 1
        entry["abnormal"] = False
        return present(entry), f"反馈记录已{action}", True
