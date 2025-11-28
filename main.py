import asyncio
import threading
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.core.message.message_event_result import MessageEventResult

from .engine.emailCli import EmailClient


@register("Orlando", "Orlando", "一个简单的插件", "1.0.0")
class OrlandoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config
        self.context.add_llm_tools()
        self.loop = None

    # =====================================================================
    # ★★★ 线程安全发送消息 ★★★
    # =====================================================================
    def send_message(self, unified_msg_origin: str, data: dict):
        """线程安全地发送消息到 AstrBot"""
        logger.info(f"[Thread] 发送提醒: {data['text']}  to  {unified_msg_origin}")
        try:
            # 生成协程
            coro = self.context.send_message(
                unified_msg_origin,
                MessageEventResult().message(data["text"]),
            )
            # 将协程提交到事件循环执行（线程安全）
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)  # type: ignore
            # 返回 future 以便可选地检查执行情况
            return future
        except Exception as e:
            logger.error(f"线程中调度协程失败: {e}")

    # =====================================================================
    # ★★★ 邮件回调（后台线程调用） ★★★
    # {"subject": subject, "from": from_, "date": date_, "body": body}
    # =====================================================================
    def push_email(self, uid, email_info):
        """
        被 EmailClient 线程调用
        线程安全地调用异步 LLM 获取验证码并发送消息
        """
        # 获取消息目标
        umo = f"久川:FriendMessage:{self.config.get('id')}"
        # 1. 构建 prompt
        email_body = email_info["body"]
        prompt = f"""
        你是一名智能邮件解析助手，请分析下面的邮件正文。

        任务：
        1. 判断该邮件是否包含验证码（verification code、验证码、安全码等）。
        2. 如果是验证码邮件：
        - 提取验证码，验证码一般为 4-8 位，由数字和/或字母组成。
        - 若有多个候选验证码，优先识别被描述为“验证码”“安全码”“verification code”“code”等关键词附近的内容。
        - 仅输出验证码，不要输出任何附加文字。
        3. 如果不是验证码邮件，直接输出：None

        邮件正文如下：
        {email_body}
        """
        # 2. 获取主事件循环
        loop = (
            self.loop
        )  # 需要在 initialize() 中保存：self.loop = asyncio.get_running_loop()
        # 3. 获取聊天模型 ID 的协程
        coro_provider = self.context.get_current_chat_provider_id(umo=umo)
        provider_id = asyncio.run_coroutine_threadsafe(coro_provider, loop).result(timeout=5)  # type: ignore
        # 4. 调用 LLM 获取验证码（线程安全提交）
        coro_llm = self.context.llm_generate(
            chat_provider_id=provider_id, prompt=prompt
        )
        llm_resp = asyncio.run_coroutine_threadsafe(coro_llm, loop).result(timeout=10)  # type: ignore
        code = llm_resp.completion_text.strip()
        # 5. 如果 LLM 返回 None，则不发送消息
        if code == "None":
            return  # 不是验证码邮件，直接返回
        # 6. 构建发送消息协程并提交
        msg_coro = self.send_message(
            umo,
            {"text": f"收到验证码邮件：{email_info['subject']}，验证码：{code}"},
        )
        asyncio.run_coroutine_threadsafe(msg_coro, loop)  # type: ignore

    # =====================================================================
    # ★★★ 插件初始化（异步） ★★★
    # =====================================================================
    async def initialize(self):
        """插件初始化，启动后台监听邮件线程"""
        # 1. 获取主事件循环（关键）
        self.loop = asyncio.get_running_loop()
        logger.info("启动邮件监听线程，账号：" + self.config["email_addr"])
        # 2. 初始化邮件客户端
        client = EmailClient(self.config["email_addr"], self.config["email_pass"])
        # 3. 启动后台线程
        thread = threading.Thread(
            target=client.start_listening, args=(self.push_email,), daemon=True
        )
        thread.start()
        logger.info("邮件监听线程已启动。")

    # =====================================================================
    # ★★★ 插件销毁 ★★★
    # =====================================================================
    async def terminate(self):
        """插件被卸载时执行"""
        logger.info("OrlandoPlugin 已终止。")