import asyncio
import threading
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from .engine.emailCli import EmailClient


@register("Orlando", "Orlando", "一个简单的插件", "1.0.0")
class OrlandoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config
        self.loop = None  # 用于保存主事件循环（非常关键）

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
        你是一名智能邮件解析助手，请从下面的邮件正文中提取“验证码”。

        要求：
        1. 验证码一般为 4-8 位数字。
        2. 若有多个数字，优先识别被描述为“验证码”“安全码”“verification code”“code”等关键词附近的数字。
        3. 如果找到验证码，仅输出纯数字，不要输出任何附加文字。
        4. 如果未找到验证码，只输出：NOT_FOUND

        邮件正文如下：
        {email_body}
        """
                
        # 2. 获取主事件循环
        loop = (
            self.loop
        )  # 需要在 initialize() 中保存：self.loop = asyncio.get_running_loop()

        # 3. 获取聊天模型 ID 的协程
        coro_provider = self.context.get_current_chat_provider_id(umo=umo)
        provider_id = asyncio.run_coroutine_threadsafe(coro_provider, loop).result(  # type: ignore
            timeout=5
        )

        # 4. 调用 LLM 获取验证码（线程安全提交）
        coro_llm = self.context.llm_generate(
            chat_provider_id=provider_id, prompt=prompt
        )
        llm_resp = asyncio.run_coroutine_threadsafe(coro_llm, loop).result(timeout=10)  # type: ignore

        # 5. 构建发送消息协程并提交
        msg_coro = self.send_message(
            umo,
            {
                "text": f"收到验证码邮件：{email_info['subject']}，验证码：{llm_resp.completion_text}"
            },
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
