"""状态管理：持久化 historyId 和已处理邮件 ID"""

import json
import logging
import os
from collections import OrderedDict

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "state.json"
MAX_PROCESSED_IDS = 1000  # 最多缓存最近 1000 个已处理 ID


class State:
    """管理转发状态，防止重启后重复处理"""

    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self.state_file = state_file
        self.history_id: str = ""
        self.processed_ids: OrderedDict[str, None] = OrderedDict()

        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            logger.info("状态文件不存在，将从当前状态开始")
            return

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            self.history_id = data.get("history_id", "")
            ids = data.get("processed_ids", [])
            self.processed_ids = OrderedDict.fromkeys(ids)
            logger.info(
                "已加载状态: historyId=%s, 已处理邮件=%d",
                self.history_id,
                len(self.processed_ids),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("状态文件读取失败，将重新开始: %s", e)

    def save(self) -> None:
        data = {
            "history_id": self.history_id,
            "processed_ids": list(self.processed_ids.keys()),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_processed(self, msg_id: str) -> bool:
        return msg_id in self.processed_ids

    def mark_processed(self, msg_id: str) -> None:
        self.processed_ids[msg_id] = None
        # 超出上限时移除最旧的
        while len(self.processed_ids) > MAX_PROCESSED_IDS:
            self.processed_ids.popitem(last=False)

    def update_history_id(self, history_id: str) -> None:
        self.history_id = history_id
