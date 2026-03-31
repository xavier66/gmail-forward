"""邮件过滤引擎：按规则匹配邮件"""

import logging
from email.utils import parseaddr

from src.config import Rule

logger = logging.getLogger(__name__)


def match_rules(
    message: dict, rules: list[Rule]
) -> list[tuple[Rule, dict]]:
    """对邮件应用所有规则，返回匹配的 (规则, 邮件详情) 列表"""
    matches = []
    for rule in rules:
        if _match_rule(message, rule):
            logger.info("邮件 '%s' 匹配规则 '%s'", message.get("subject", ""), rule.name)
            matches.append((rule, message))
    return matches


def _match_rule(message: dict, rule: Rule) -> bool:
    """检查邮件是否匹配某条规则的所有条件（AND 关系）"""
    cond = rule.conditions

    if cond.from_ and not _match_from(message, cond.from_):
        return False

    if cond.subject_contains and not _match_subject(message, cond.subject_contains):
        return False

    return True


def _match_from(message: dict, patterns: list[str]) -> bool:
    """发件人匹配：精确地址或 @domain.com 域名通配"""
    _, from_addr = parseaddr(message.get("from", ""))
    from_addr = from_addr.lower()

    for pattern in patterns:
        pattern = pattern.lower().strip()
        if pattern.startswith("@"):
            if from_addr.endswith(pattern) or from_addr.split("@", 1)[-1] == pattern[1:]:
                return True
        else:
            if from_addr == pattern:
                return True

    return False


def _match_subject(message: dict, keywords: list[str]) -> bool:
    """主题关键词匹配（OR 关系，大小写不敏感）"""
    subject = message.get("subject", "").lower()
    return any(kw.lower() in subject for kw in keywords)
