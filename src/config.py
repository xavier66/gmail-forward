"""加载和验证 YAML 配置文件"""

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class GmailConfig:
    client_secret_file: str = "credentials/client_secret.json"
    token_file: str = "credentials/token.json"


@dataclass
class PollConfig:
    interval_seconds: int = 5


@dataclass
class Condition:
    from_: list[str] = field(default_factory=list)
    subject_contains: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


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
        labels=data.get("labels", []),
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
            client_secret_file=data.get("gmail", {}).get(
                "client_secret_file", GmailConfig.client_secret_file
            ),
            token_file=data.get("gmail", {}).get(
                "token_file", GmailConfig.token_file
            ),
        ),
        poll=PollConfig(
            interval_seconds=data.get("poll", {}).get(
                "interval_seconds", PollConfig.interval_seconds
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
    if config.poll.interval_seconds < 1:
        raise ValueError("poll.interval_seconds 不能小于 1 秒")

    for i, rule in enumerate(config.rules):
        if not rule.forward_to:
            raise ValueError(f"规则 '{rule.name}' (第 {i + 1} 条) 缺少 forward_to")
        if not rule.conditions.from_ and not rule.conditions.subject_contains and not rule.conditions.labels:
            raise ValueError(
                f"规则 '{rule.name}' (第 {i + 1} 条) 至少需要一个过滤条件"
            )
