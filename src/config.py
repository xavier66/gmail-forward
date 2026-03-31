"""加载和验证 YAML 配置文件"""

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class GmailConfig:
    email: str = ""
    app_password: str = ""


@dataclass
class PollConfig:
    interval_seconds: int = 5
    fetch_within_hours: int = 1
    fetch_max_count: int = 100


@dataclass
class Condition:
    from_: list[str] = field(default_factory=list)
    subject_contains: list[str] = field(default_factory=list)


@dataclass
class Rule:
    name: str = ""
    conditions: Condition = field(default_factory=Condition)
    forward_to: list[str] = field(default_factory=list)


@dataclass
class ForwardConfig:
    add_prefix: bool = True
    include_original_headers: bool = True


@dataclass
class AppConfig:
    gmail: GmailConfig = field(default_factory=GmailConfig)
    poll: PollConfig = field(default_factory=PollConfig)
    rules: list[Rule] = field(default_factory=list)
    forward: ForwardConfig = field(default_factory=ForwardConfig)


def _parse_condition(data: dict[str, Any]) -> Condition:
    return Condition(
        from_=data.get("from", []),
        subject_contains=data.get("subject_contains", []),
    )


def _parse_rule(data: dict[str, Any]) -> Rule:
    return Rule(
        name=data.get("name", "未命名规则"),
        conditions=_parse_condition(data.get("conditions", {})),
        forward_to=data.get("forward_to", []),
    )


def load_config(path: str = "config.yaml") -> AppConfig:
    """从 YAML 文件加载配置"""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"配置文件不存在: {path}\n请复制 config.yaml.example 为 config.yaml 并填写配置"
        )

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError("配置文件为空")

    config = AppConfig(
        gmail=GmailConfig(
            email=data.get("gmail", {}).get("email", ""),
            app_password=data.get("gmail", {}).get("app_password", ""),
        ),
        poll=PollConfig(
            interval_seconds=data.get("poll", {}).get(
                "interval_seconds", PollConfig.interval_seconds
            ),
            fetch_within_hours=data.get("poll", {}).get(
                "fetch_within_hours", PollConfig.fetch_within_hours
            ),
            fetch_max_count=data.get("poll", {}).get(
                "fetch_max_count", PollConfig.fetch_max_count
            ),
        ),
        rules=[_parse_rule(r) for r in data.get("rules", [])],
        forward=ForwardConfig(
            add_prefix=data.get("forward", {}).get(
                "add_prefix", ForwardConfig.add_prefix
            ),
            include_original_headers=data.get("forward", {}).get(
                "include_original_headers", ForwardConfig.include_original_headers
            ),
        ),
    )

    _validate(config)
    return config


def _validate(config: AppConfig) -> None:
    """验证配置合法性"""
    if not config.gmail.email:
        raise ValueError("gmail.email 不能为空")
    if not config.gmail.app_password:
        raise ValueError("gmail.app_password 不能为空")
    if config.poll.interval_seconds < 1:
        raise ValueError("poll.interval_seconds 不能小于 1 秒")

    for i, rule in enumerate(config.rules):
        if not rule.forward_to:
            raise ValueError(f"规则 '{rule.name}' (第 {i + 1} 条) 缺少 forward_to")
        if not rule.conditions.from_ and not rule.conditions.subject_contains:
            raise ValueError(
                f"规则 '{rule.name}' (第 {i + 1} 条) 至少需要一个过滤条件"
            )
