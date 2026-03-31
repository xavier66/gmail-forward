"""IMAP 客户端：连接 Gmail 并获取新邮件"""

import email
import imaplib
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header

logger = logging.getLogger(__name__)

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


class IMAPClient:
    """Gmail IMAP 客户端"""

    def __init__(self, email_addr: str, app_password: str):
        self.email_addr = email_addr
        self.app_password = app_password
        self.conn: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        """连接并登录 IMAP 服务器"""
        self.conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        self.conn.login(self.email_addr, self.app_password)
        self.conn.select("INBOX")
        logger.info("IMAP 连接成功: %s", self.email_addr)

    def disconnect(self) -> None:
        if self.conn:
            try:
                self.conn.close()
                self.conn.logout()
            except Exception:
                pass
            self.conn = None

    def ensure_connected(self) -> None:
        """确保连接可用，断线自动重连"""
        try:
            if self.conn:
                self.conn.noop()
                return
        except Exception:
            logger.warning("IMAP 连接断开，正在重连...")
        self.connect()

    def fetch_unseen(self, within_hours: int = 1, max_count: int = 100) -> list[dict]:
        """获取未读邮件，限定时间范围和最大数量"""
        self.ensure_connected()

        since_date = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).strftime("%d-%b-%Y")
        _, msg_ids = self.conn.search(None, "UNSEEN", f'(SINCE "{since_date}")')
        if not msg_ids[0]:
            return []

        id_list = msg_ids[0].split()
        id_list = id_list[-max_count:]  # 取最近的 N 封

        messages = []
        for mid in id_list:
            msg = self._fetch_message(mid)
            if msg:
                messages.append(msg)
        return messages

    def _fetch_message(self, msg_id: bytes) -> dict | None:
        """获取单封邮件详情"""
        _, data = self.conn.fetch(msg_id, "(RFC822)")
        if not data or not data[0]:
            return None

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = _decode_header_value(msg.get("Subject", ""))
        from_addr = _decode_header_value(msg.get("From", ""))
        to_addr = _decode_header_value(msg.get("To", ""))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", msg_id.decode())

        body_plain = _extract_body(msg, "text/plain")
        body_html = _extract_body(msg, "text/html")

        return {
            "id": message_id,
            "imap_id": msg_id,
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "date": date_str,
            "body_plain": body_plain,
            "body_html": body_html,
            "raw": raw_email,
        }


def _decode_header_value(value: str) -> str:
    """解码邮件头（处理编码的中文等）"""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_body(msg: email.message.Message, mime_type: str) -> str:
    """从邮件中提取指定 MIME 类型的正文"""
    if msg.get_content_type() == mime_type:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        return ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == mime_type:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

    return ""
