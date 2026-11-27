import logging
import smtplib
import uuid
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """邮件后端发送失败"""

    pass


class EmailSender(Protocol):
    """邮件发送器接口"""

    def send(self, to_email: str, subject: str, body: str) -> str:
        """发送纯文本邮件，返回 provider message id。"""
        ...


def _email_domain(to_email: str) -> str:
    """提取邮件域名"""
    _, _, domain = to_email.partition("@")
    return domain or "-"


class ConsoleEmailSender:
    """本地演示后端：只记录发送事件，不连接网络。"""

    def send(self, to_email: str, subject: str, body: str) -> str:
        logger.info(
            "email_console_sent",
            extra={
                "to_domain": _email_domain(to_email),
                "subject_len": len(subject),
            },
        )
        return f"console:{uuid.uuid4().hex}"


class SmtpEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        email_from: str,
        username: str | None = None,
        auth_code: str | None = None,
        use_tls: bool = True,
        timeout_seconds: int = 10,
    ):
        self.host = host
        self.port = port
        self.email_from = email_from
        self.username = username
        self.auth_code = auth_code
        self.use_tls = use_tls
        self.timeout_seconds = timeout_seconds

    def send(self, to_email: str, subject: str, body: str) -> str:
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self.host, self.port, timeout=self.timeout_seconds
            ) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()
                if self.username:
                    server.login(self.username, self.auth_code or "")
                server.send_message(message)
        except Exception as exc:
            raise EmailSendError(f"{type(exc).__name__}: {exc}") from exc

        return message.get("Message-ID") or f"smtp:{uuid.uuid4().hex}"


def build_email_sender(settings) -> EmailSender:
    """根据配置构建邮件发送器"""
    backend = (settings.email_backend or "console").strip().lower()
    if backend == "console":
        return ConsoleEmailSender()
    if backend == "smtp":
        if not settings.smtp_host:
            raise ValueError("EMAIL_BACKEND=smtp 时必须配置 SMTP_HOST")
        if not settings.email_from:
            raise ValueError("EMAIL_BACKEND=smtp 时必须配置 EMAIL_FROM")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            email_from=settings.email_from,
            username=settings.smtp_username,
            auth_code=settings.smtp_auth_code,
            use_tls=settings.smtp_use_tls,
            timeout_seconds=settings.smtp_timeout_seconds,
        )
    raise ValueError(f"未知 EMAIL_BACKEND: {settings.email_backend}")
