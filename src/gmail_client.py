"""Gmail API 封装：历史查询、邮件获取、邮件发送"""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailClient:
    """Gmail API 客户端"""

    def __init__(self, creds: Credentials):
        self.service = build("gmail", "v1", credentials=creds)

    def get_current_history_id(self) -> str:
        """获取当前邮箱的 historyId（用作增量起点）"""
        profile = self.service.users().getProfile(userId="me").execute()
        history_id = profile["historyId"]
        logger.info("当前 profile historyId: %s", history_id)
        return history_id

    def get_history(self, start_history_id: str) -> list[dict]:
        """获取自 start_history_id 以来的新邮件消息列表"""
        messages = []
        try:
            results = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                )
                .execute()
            )
        except HttpError as e:
            if e.status_code == 404:
                logger.warning("historyId %s 已过期，将获取最新邮件", start_history_id)
                return self._get_recent_messages()
            raise

        histories = results.get("history", [])
        for hist in histories:
            for msg_added in hist.get("messagesAdded", []):
                msg = msg_added.get("message", {})
                messages.append(
                    {"id": msg["id"], "threadId": msg.get("threadId"), "labelIds": msg.get("labelIds", [])}
                )

        # 处理分页
        page_token = results.get("nextPageToken")
        while page_token:
            results = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    pageToken=page_token,
                )
                .execute()
            )
            for hist in results.get("history", []):
                for msg_added in hist.get("messagesAdded", []):
                    msg = msg_added.get("message", {})
                    messages.append(
                        {"id": msg["id"], "threadId": msg.get("threadId"), "labelIds": msg.get("labelIds", [])}
                    )
            page_token = results.get("nextPageToken")

        return messages

    def _get_recent_messages(self) -> list[dict]:
        """当 historyId 过期时，获取最近邮件作为回退"""
        results = (
            self.service.users()
            .messages()
            .list(userId="me", maxResults=10)
            .execute()
        )
        messages = []
        for msg in results.get("messages", []):
            messages.append(
                {"id": msg["id"], "threadId": msg.get("threadId"), "labelIds": []}
            )
        return messages

    def get_message_detail(self, msg_id: str) -> dict | None:
        """获取邮件完整信息：headers、正文、标签"""
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except HttpError as e:
            logger.error("获取邮件 %s 失败: %s", msg_id, e)
            return None

        headers = {}
        for h in msg.get("payload", {}).get("headers", []):
            headers[h["name"].lower()] = h["value"]

        return {
            "id": msg["id"],
            "threadId": msg.get("threadId"),
            "labelIds": msg.get("labelIds", []),
            "snippet": msg.get("snippet", ""),
            "headers": headers,
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body_plain": _extract_body(msg, "text/plain"),
            "body_html": _extract_body(msg, "text/html"),
            "raw": msg.get("raw"),
        }

    def get_raw_message(self, msg_id: str) -> bytes | None:
        """获取邮件原始 RFC2822 内容（用于转发）"""
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="raw")
                .execute()
            )
        except HttpError as e:
            logger.error("获取原始邮件 %s 失败: %s", msg_id, e)
            return None

        raw = msg.get("raw")
        if raw:
            return base64.urlsafe_b64decode(raw.encode("utf-8"))
        return None

    def send_message(self, mime_message: MIMEMultipart) -> str | None:
        """发送邮件，返回发送的消息 ID"""
        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")
        try:
            result = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
            logger.info("邮件已发送，ID: %s", result["id"])
            return result["id"]
        except HttpError as e:
            logger.error("发送邮件失败: %s", e)
            return None


def _extract_body(msg: dict, mime_type: str) -> str:
    """从邮件 payload 中提取指定 MIME 类型的正文"""
    payload = msg.get("payload", {})

    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == mime_type:
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
        # 递归处理嵌套 multipart
        for sub in part.get("parts", []):
            if sub.get("mimeType") == mime_type:
                data = sub.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    return ""
