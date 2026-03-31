"""邮件转发：构建转发 MIME 消息并通过 Gmail API 发送"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from src.config import ForwardConfig, Rule
from src.gmail_client import GmailClient

logger = logging.getLogger(__name__)


def forward_message(
    client: GmailClient,
    message: dict,
    rule: Rule,
    forward_config: ForwardConfig,
) -> str | None:
    """构建并转发邮件，返回发送的消息 ID 或 None"""
    original_raw = client.get_raw_message(message["id"])
    if not original_raw:
        logger.error("无法获取原始邮件 %s，跳过转发", message["id"])
        return None

    # 获取原始邮件的发件人用于 display
    original_from = message.get("from", "")
    original_subject = message.get("subject", "")
    original_date = message.get("date", "")

    for recipient in rule.forward_to:
        fwd_msg = _build_forward_message(
            to=recipient,
            original_from=original_from,
            original_subject=original_subject,
            original_date=original_date,
            original_raw=original_raw,
            forward_config=forward_config,
        )
        msg_id = client.send_message(fwd_msg)
        if msg_id:
            logger.info(
                "已转发邮件 '%s' → %s (规则: %s)",
                original_subject,
                recipient,
                rule.name,
            )
        else:
            logger.error("转发失败: '%s' → %s", original_subject, recipient)

    return rule.forward_to[0]  # 返回值仅用于日志


def _build_forward_message(
    to: str,
    original_from: str,
    original_subject: str,
    original_date: str,
    original_raw: bytes,
    forward_config: ForwardConfig,
) -> MIMEMultipart:
    """构建转发的 MIME 消息"""
    fwd_subject = f"Fwd: {original_subject}"
    if forward_config.add_prefix:
        fwd_subject = f"[转发] {original_subject}"

    fwd_msg = MIMEMultipart("mixed")
    fwd_msg["To"] = to
    fwd_msg["Subject"] = fwd_subject
    fwd_msg["Date"] = formatdate(localtime=True)

    # 正文部分
    body_parts = []
    if forward_config.include_original_headers:
        body_parts.append(f"---------- 转发邮件 ----------")
        body_parts.append(f"发件人: {original_from}")
        body_parts.append(f"日期: {original_date}")
        body_parts.append(f"主题: {original_subject}")
        body_parts.append("")

    body_text = "\n".join(body_parts)
    fwd_msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # 附加原始邮件
    from email.mime.message import MIMEMessage
    import email

    original_email = email.message_from_bytes(original_raw)
    fwd_msg.attach(MIMEMessage(original_email))

    return fwd_msg
