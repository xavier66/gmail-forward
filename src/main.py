"""Gmail 条件转发工具 - 主入口"""

import logging
import signal
import sys
import time

from src.auth import get_credentials
from src.config import load_config
from src.filter_engine import match_rules
from src.forwarder import forward_message
from src.gmail_client import GmailClient
from src.state import State

logger = logging.getLogger("gmail-forward")

# 全局退出标志
_shutdown = False


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def handle_signal(signum, frame):
    global _shutdown
    sig_name = signal.Signals(signum).name
    logger.info("收到信号 %s，正在优雅退出...", sig_name)
    _shutdown = True


def poll_loop(client: GmailClient, config, state: State) -> None:
    """主轮询循环"""
    interval = config.poll.interval_seconds

    while not _shutdown:
        try:
            _poll_once(client, config, state)
        except Exception:
            logger.exception("轮询出错")

        # 分段 sleep，方便响应信号
        for _ in range(interval):
            if _shutdown:
                break
            time.sleep(1)


def _poll_once(client: GmailClient, config, state: State) -> None:
    """执行一次轮询"""
    if not state.history_id:
        state.update_history_id(client.get_current_history_id())
        state.save()
        logger.info("初始化 historyId: %s（跳过已有邮件）", state.history_id)
        return

    messages = client.get_history(state.history_id)
    if not messages:
        return

    logger.info("发现 %d 封新邮件", len(messages))

    # 获取最新的 historyId（从最后一条 history 记录）
    # 注意：get_history 返回的消息列表没有 historyId，
    # 我们在处理完所有邮件后更新为当前 profile 的 historyId
    forwarded_count = 0

    for msg_summary in messages:
        if _shutdown:
            break

        msg_id = msg_summary["id"]

        if state.is_processed(msg_id):
            continue

        # 跳过自己发出的邮件（避免转发循环）
        label_ids = msg_summary.get("labelIds", [])
        if "SENT" in label_ids:
            state.mark_processed(msg_id)
            continue

        detail = client.get_message_detail(msg_id)
        if not detail:
            continue

        # 合并 history 中已有的 labelIds
        if not detail.get("labelIds") and label_ids:
            detail["labelIds"] = label_ids

        # 过滤匹配
        matches = match_rules(detail, config.rules)
        if not matches:
            state.mark_processed(msg_id)
            continue

        # 转发匹配的邮件
        for rule, _ in matches:
            try:
                forward_message(client, detail, rule, config.forward)
                forwarded_count += 1
            except Exception:
                logger.exception("转发邮件 %s 失败", msg_id)

        state.mark_processed(msg_id)

    # 更新 historyId 为当前值
    state.update_history_id(client.get_current_history_id())
    state.save()

    if forwarded_count:
        logger.info("本次转发 %d 封邮件", forwarded_count)


def main() -> None:
    setup_logging()
    logger.info("Gmail 条件转发工具启动")

    # 注册信号处理
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 加载配置
    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as e:
        logger.error("配置错误: %s", e)
        sys.exit(1)

    logger.info("已加载 %d 条转发规则", len(config.rules))

    # 认证
    try:
        creds = get_credentials(config.gmail.client_secret_file, config.gmail.token_file)
    except FileNotFoundError as e:
        logger.error("认证失败: %s", e)
        sys.exit(1)

    # 初始化客户端和状态
    client = GmailClient(creds)
    state = State()

    logger.info(
        "开始轮询（间隔 %d 秒），按 Ctrl+C 退出",
        config.poll.interval_seconds,
    )

    # 进入主循环
    poll_loop(client, config, state)

    # 保存最终状态
    state.save()
    logger.info("已退出")


if __name__ == "__main__":
    main()
