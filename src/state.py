"""状态管理：持久化已处理邮件 ID，防止重复转发"""

import json
import logging
import os
from collections import OrderedDict

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "state.json"
MAX_PROCESSED_IDS = 1000


class State:
    """管理转发状态，防止重启后重复处理"""

    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self.state_file = state_file
        self.processed_ids: OrderedDict[str, None] = OrderedDict()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("processed_ids", [])
            self.processed_ids = OrderedDict.fromkeys(ids)
            logger.info("已加载状态: 已处理邮件 %d 封", len(self.processed_ids))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("状态文件读取失败: %s", e)

    def save(self) -> None:
        data = {"processed_ids": list(self.processed_ids.keys())}
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_processed(self, msg_id: str) -> bool:
        return msg_id in self.processed_ids

    def mark_processed(self, msg_id: str) -> None:
        self.processed_ids[msg_id] = None
        while len(self.processed_ids) > MAX_PROCESSED_IDS:
            self.processed_ids.popitem(last=False)
