"""邮件转发：通过 SMTP 转发邮件"""

import logging
import smtplib
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from src.config import ForwardConfig, Rule

logger = logging.getLogger(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def forward_message(
    email_addr: str,
    app_password: str,
    message: dict,
    rule: Rule,
    forward_config: ForwardConfig,
) -> bool:
    """转发邮件到指定收件人，返回是否成功"""
    raw = message.get("raw")
    if not raw:
        logger.error("邮件无原始数据，跳过: %s", message.get("subject", ""))
        return False
    original_email = email.message_from_bytes(raw)

    sent_count = 0
    for recipient in rule.forward_to:
        try:
            fwd_msg = _build_forward(
                from_addr=email_addr,
                to=recipient,
                original_from=message.get("from", ""),
                original_subject=message.get("subject", ""),
                original_date=message.get("date", ""),
                original_raw=original_email,
                forward_config=forward_config,
            )
            _send_smtp(email_addr, app_password, fwd_msg)
            sent_count += 1
            logger.info("已转发 '%s' → %s", message.get("subject", ""), recipient)
        except Exception:
            logger.exception("转发失败 '%s' → %s", message.get("subject", ""), recipient)

    return sent_count > 0


def _build_forward(
    from_addr: str,
    to: str,
    original_from: str,
    original_subject: str,
    original_date: str,
    original_raw,
    forward_config: ForwardConfig,
) -> MIMEMultipart:
    """构建转发邮件"""
    subject = original_subject
    if forward_config.add_prefix:
        subject = f"[转发] {original_subject}"
    else:
        subject = f"Fwd: {subject}"

    fwd = MIMEMultipart("mixed")
    fwd["From"] = from_addr
    fwd["To"] = to
    fwd["Subject"] = subject
    fwd["Date"] = formatdate(localtime=True)

    # 正文
    body_parts = []
    if forward_config.include_original_headers:
        body_parts.append("---------- 转发邮件 ----------")
        body_parts.append(f"发件人: {original_from}")
        body_parts.append(f"日期: {original_date}")
        body_parts.append(f"主题: {original_subject}")
        body_parts.append("")

    fwd.attach(MIMEText("\n".join(body_parts), "plain", "utf-8"))

    # 附加原始邮件
    fwd.attach(MIMEMessage(original_raw))

    return fwd


def _send_smtp(
    email_addr: str, app_password: str, msg: MIMEMultipart
) -> None:
    """通过 Gmail SMTP 发送邮件"""
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(email_addr, app_password)
        server.send_message(msg)
