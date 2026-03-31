"""状态管理：持久化已处理邮件 ID 和轮询历史，防止重复转发"""

import json
import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "state.json"
MAX_PROCESSED_IDS = 1000
MAX_HISTORY_ROUNDS = 50  # 最多保留最近 50 轮记录


class State:
    """管理转发状态，防止重启后重复处理"""

    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self.state_file = state_file
        self.processed_ids: OrderedDict[str, None] = OrderedDict()
        self.last_poll_time: str = ""
        self.poll_history: list[dict] = []
        self._current_round: dict | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("processed_ids", [])
            self.processed_ids = OrderedDict.fromkeys(ids)
            self.last_poll_time = data.get("last_poll_time", "")
            self.poll_history = data.get("poll_history", [])
            logger.info(
                "已加载状态: 已处理邮件 %d 封, 上次轮询 %s",
                len(self.processed_ids),
                self.last_poll_time or "无",
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("状态文件读取失败: %s", e)

    def save(self) -> None:
        data = {
            "processed_ids": list(self.processed_ids.keys()),
            "last_poll_time": self.last_poll_time,
            "poll_history": self.poll_history,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_processed(self, msg_id: str) -> bool:
        return msg_id in self.processed_ids

    def mark_processed(self, msg_id: str) -> None:
        self.processed_ids[msg_id] = None
        while len(self.processed_ids) > MAX_PROCESSED_IDS:
            self.processed_ids.popitem(last=False)

    def begin_round(self) -> None:
        """开始新一轮轮询"""
        self._current_round = {
            "time": datetime.now(timezone.utc).isoformat(),
            "fetched": [],
            "forwarded": [],
            "skipped": [],
        }

    def record_fetched(self, msg_id: str, subject: str) -> None:
        if self._current_round:
            self._current_round["fetched"].append({"id": msg_id, "subject": subject})

    def record_forwarded(self, msg_id: str, subject: str, rule_name: str, recipients: list[str]) -> None:
        if self._current_round:
            self._current_round["forwarded"].append({
                "id": msg_id,
                "subject": subject,
                "rule": rule_name,
                "to": recipients,
            })

    def record_skipped(self, msg_id: str, subject: str, reason: str) -> None:
        if self._current_round:
            self._current_round["skipped"].append({"id": msg_id, "subject": subject, "reason": reason})

    def end_round(self) -> None:
        """结束本轮轮询，保存记录"""
        if not self._current_round:
            return

        self.last_poll_time = self._current_round["time"]
        self.poll_history.append(self._current_round)

        # 超出上限时移除最旧的
        while len(self.poll_history) > MAX_HISTORY_ROUNDS:
            self.poll_history.pop(0)

        self._current_round = None
