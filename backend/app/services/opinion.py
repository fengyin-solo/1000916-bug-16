"""客户反馈业务规则：状态流转、字段校验、幂等与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "opinion"
REQUIRED_FIELDS = ["反馈编号", "委托单位", "反馈类型"]
# 处理完成时必须同时提交的结论字段
CONCLUSION_FIELDS = ["处理人员", "处理结果"]
STATUS_ORDER = ["待受理", "处理中", "已处理", "已关闭"]
ACTION_RULES = {"受理反馈": "处理中", "处理完成": "已处理", "关闭反馈": "已关闭"}
NEGATIVE_ACTIONS: list[str] = []


def serialize(entry: dict[str, Any]) -> dict[str, Any]:
    """对外返回的统一口径：反馈状态始终跟随流转状态，未受理的记录不提前暴露处理结论。

    受理页面、详情、处理弹窗都走这个口径，保证三处看到的反馈结论一致。
    """
    row = dict(entry)
    status = str(row.get("status") or STATUS_ORDER[0])
    row["反馈状态"] = status
    if status == STATUS_ORDER[0]:
        row["处理人员"] = None
        row["处理结果"] = None
    return row


class OpinionService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        client: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("反馈编号", ""))]
        if client:
            rows = [row for row in rows if client in str(row.get("委托单位", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("反馈类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [serialize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return serialize(entry) if entry is not None else None

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], str]:
        """登记反馈记录。

        返回 (记录, 缺失字段, 说明)。反馈编号重复时不新增记录，只把已登记的记录
        原样返回，保证重复提交只生效一次，重试时也不会冒出第二条同编号记录。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""

        rows = store.rows(MODULE)
        code = str(values["反馈编号"]).strip()
        for row in rows:
            if str(row.get("反馈编号") or "").strip() == code:
                return serialize(row), [], f"反馈编号 {code} 已登记过，重复提交只生效一次"

        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values[field]).strip() for field in REQUIRED_FIELDS})
        for field in ("反馈内容", "反馈日期"):
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return serialize(entry), [], "反馈记录已登记"

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        """执行受理反馈、处理完成、关闭反馈。

        - 已处于目标状态：幂等返回，只生效一次，不报错、不重复处理；
        - 状态回退、已关闭再操作：拦下并给出原因；
        - 处理完成：处理人员、处理结果不能为空，缺哪个说明哪个，不做静默退回。
        """
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"反馈记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于客户反馈可执行范围"

        target = ACTION_RULES[action]
        current = str(entry.get("status") or "")

        # 幂等：网络重试或重复点击时，直接返回当前记录，只生效一次。
        if current == target:
            return serialize(entry), f"反馈记录已处于「{target}」，重复提交只生效一次"
        if current == STATUS_ORDER[-1]:
            return None, f"反馈记录已关闭，不能再执行「{action}」，如需继续请先确认记录状态"
        if current in STATUS_ORDER and STATUS_ORDER.index(target) <= STATUS_ORDER.index(current):
            return None, f"反馈记录当前为「{current}」，不能回退执行「{action}」"

        if action == "处理完成":
            missing = [
                field for field in CONCLUSION_FIELDS
                if not str(values.get(field) or "").strip()
            ]
            if missing:
                return None, f"处理结果未提交：{'、'.join(missing)}不能为空，请补充后重新提交"
            entry["处理人员"] = str(values["处理人员"]).strip()
            entry["处理结果"] = str(values["处理结果"]).strip()

        entry["status"] = target
        entry["pending"] = target in (STATUS_ORDER[0], STATUS_ORDER[1])
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return serialize(entry), f"反馈记录已{action}"
