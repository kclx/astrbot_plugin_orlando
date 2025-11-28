#!/usr/bin/env python3
"""
email_client_threadsafe.py

功能：
- 封装 163 邮箱轮询监听新邮件逻辑
- 提供 EmailClient 类供主程序调用
- 支持线程安全调用异步回调（如 LLM 提取验证码和发送消息）
"""

import time
import asyncio
from typing import Callable
from imapclient import IMAPClient
from email import message_from_bytes
from email.header import decode_header

class EmailClient:
    def __init__(
        self,
        email_addr: str,
        email_pass: str,
        imap_host: str = "imap.163.com",
        mailbox: str = "INBOX",
        poll_interval: int = 10,
        loop: asyncio.AbstractEventLoop = None,  # type: ignore
    ):
        """
        初始化 EmailClient
        :param email_addr: 邮箱地址
        :param email_pass: 邮箱客户端授权码
        :param imap_host: IMAP服务器
        :param mailbox: 监听文件夹，默认收件箱
        :param poll_interval: 轮询间隔（秒）
        :param loop: 主事件循环，用于线程安全调度协程
        """
        self.email_addr = email_addr
        self.email_pass = email_pass
        self.imap_host = imap_host
        self.mailbox = mailbox
        self.poll_interval = poll_interval
        self.seen_uids = set()
        self.client = None
        self.loop = loop or asyncio.get_event_loop()  # 主事件循环

    @staticmethod
    def decode_str(s: str) -> str:
        """解码邮件头部"""
        decoded, charset = decode_header(s)[0]
        if isinstance(decoded, bytes):
            return decoded.decode(charset or "utf-8", errors="ignore")
        return decoded

    @staticmethod
    def parse_email(raw_email: bytes) -> dict:
        """解析邮件，返回字典信息"""
        email_msg = message_from_bytes(raw_email)
        subject = EmailClient.decode_str(email_msg.get("Subject", "(无主题)"))
        from_ = EmailClient.decode_str(email_msg.get("From", "(无发件人)"))
        date_ = EmailClient.decode_str(email_msg.get("Date", "(无日期)"))

        # 提取正文（仅文本部分）
        body = ""
        if email_msg.is_multipart():
            for part in email_msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(  # type: ignore
                        part.get_content_charset() or "utf-8", errors="ignore"
                    )
                    break
        else:
            body = email_msg.get_payload(decode=True).decode(  # type: ignore
                email_msg.get_content_charset() or "utf-8", errors="ignore"
            )

        return {"subject": subject, "from": from_, "date": date_, "body": body}

    def connect(self):
        """连接 IMAP 服务器并登录"""
        self.client = IMAPClient(self.imap_host, ssl=True)
        self.client.login(self.email_addr, self.email_pass)
        self.client.id_({"name": "IMAPClient", "version": "2.1.0"})
        self.client.select_folder(self.mailbox)
        # 程序启动时，把已有邮件标记为已处理
        existing_uids = self.client.search("ALL")
        self.seen_uids.update(existing_uids)
        print(
            f"[EmailClient] 连接成功，已有邮件 {len(existing_uids)} 封，之后只处理新邮件"
        )

    def start_listening(self, callback: Callable[[int, dict], None]):
        """
        开始监听邮箱新邮件
        :param callback: 新邮件处理回调函数，参数 (uid, email_info_dict)
                         支持异步协程函数，线程安全调度
        """
        if not self.client:
            self.connect()

        print(f"[EmailClient] 开始监听 {self.mailbox} ...")

        while True:
            try:
                if self.client:
                    uids = self.client.search("UNSEEN")
                    new_uids = [uid for uid in uids if uid not in self.seen_uids]
                    for uid in new_uids:
                        msg_data = self.client.fetch(uid, ["RFC822"])
                        raw_email = msg_data[uid][b"RFC822"]
                        email_info = self.parse_email(raw_email)  # type: ignore

                        # 判断 callback 是否为协程函数
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.run_coroutine_threadsafe(
                                callback(uid, email_info), self.loop
                            )
                        else:
                            # 普通同步回调
                            callback(uid, email_info)

                        self.seen_uids.add(uid)

            except Exception as e:
                print("[EmailClient] 监听异常：", e)

            time.sleep(self.poll_interval)
