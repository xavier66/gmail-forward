"""OAuth 2.0 认证：首次授权 + token 自动刷新"""

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = ["https://mail.google.com/"]


def get_credentials(client_secret_file: str, token_file: str) -> Credentials:
    """获取有效的 OAuth 凭据，必要时自动刷新或触发授权"""

    creds = _load_token(token_file)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("Token 已过期，正在刷新...")
        creds.refresh(Request())
        _save_token(token_file, creds)
        return creds

    logger.info("未找到有效 token，启动浏览器授权...")
    return _authorize(client_secret_file, token_file)


def _load_token(token_file: str) -> Credentials | None:
    if not os.path.exists(token_file):
        return None
    try:
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        logger.info("已加载 token: %s", token_file)
        return creds
    except Exception:
        logger.warning("Token 文件无效，将重新授权")
        return None


def _save_token(token_file: str, creds: Credentials) -> None:
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    logger.info("Token 已保存: %s", token_file)


def _authorize(client_secret_file: str, token_file: str) -> Credentials:
    if not os.path.exists(client_secret_file):
        raise FileNotFoundError(
            f"OAuth 客户端密钥文件不存在: {client_secret_file}\n"
            "请从 Google Cloud Console 下载 OAuth 2.0 客户端 ID 的 JSON 文件"
        )

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(token_file, creds)
    logger.info("授权成功")
    return creds
