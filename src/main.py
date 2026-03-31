"""Gmail 条件转发工具 - 主入口"""

import logging
import signal
import sys
import time

from src.config import load_config
from src.filter_engine import match_rules
from src.forwarder import forward_message
from src.imap_client import IMAPClient
from src.state import State

logger = logging.getLogger("gmail-forward")

_shutdown = False


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def handle_signal(signum, _frame):
    global _shutdown
    logger.info("收到信号 %s，正在优雅退出...", signal.Signals(signum).name)
    _shutdown = True


def poll_loop(client: IMAPClient, config, state: State) -> None:
    """主轮询循环"""
    interval = config.poll.interval_seconds

    while not _shutdown:
        try:
            _poll_once(client, config, state)
        except Exception:
            logger.exception("轮询出错，等待重试...")

        for _ in range(interval):
            if _shutdown:
                break
            time.sleep(1)


def _poll_once(client: IMAPClient, config, state: State) -> None:
    """执行一次轮询"""
    messages = client.fetch_unseen(
        within_hours=config.poll.fetch_within_hours,
        max_count=config.poll.fetch_max_count,
    )
    if not messages:
        return

    state.begin_round()

    subjects = [m.get("subject", "(无主题)") for m in messages]
    logger.info("拉取了 %d 封邮件: %s", len(messages), "、".join(subjects))

    forwarded_count = 0
    for msg in messages:
        if _shutdown:
            break

        msg_id = msg["id"]
        subject = msg.get("subject", "(无主题)")

        if state.is_processed(msg_id):
            state.record_skipped(msg_id, subject, "已处理")
            continue

        # 跳过自己发出的邮件
        if config.gmail.email.lower() in msg.get("from", "").lower():
            state.mark_processed(msg_id)
            state.record_skipped(msg_id, subject, "自己发出的邮件")
            continue

        state.record_fetched(msg_id, subject)

        matches = match_rules(msg, config.rules)
        if not matches:
            state.mark_processed(msg_id)
            state.record_skipped(msg_id, subject, "无匹配规则")
            continue

        for rule, _ in matches:
            try:
                forward_message(
                    config.gmail.email,
                    config.gmail.app_password,
                    msg,
                    rule,
                    config.forward,
                )
                forwarded_count += 1
                state.record_forwarded(msg_id, subject, rule.name, rule.forward_to)
                logger.info(
                    "命中规则「%s」，「%s」→ 转发成功到 %s",
                    rule.name,
                    subject,
                    "、".join(rule.forward_to),
                )
            except Exception:
                logger.exception("转发邮件失败")

        state.mark_processed(msg_id)

    state.end_round()
    state.save()
    if forwarded_count:
        logger.info("本次共转发 %d 封邮件", forwarded_count)


def main() -> None:
    setup_logging()
    logger.info("Gmail 条件转发工具启动")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as e:
        logger.error("配置错误: %s", e)
        sys.exit(1)

    logger.info("已加载 %d 条转发规则", len(config.rules))

    client = IMAPClient(config.gmail.email, config.gmail.app_password)
    try:
        client.connect()
    except Exception as e:
        logger.error("IMAP 连接失败: %s（请检查邮箱和应用专用密码）", e)
        sys.exit(1)

    state = State()

    logger.info("开始轮询（间隔 %d 秒），按 Ctrl+C 退出", config.poll.interval_seconds)

    try:
        poll_loop(client, config, state)
    finally:
        state.save()
        client.disconnect()
        logger.info("已退出")


if __name__ == "__main__":
    main()
