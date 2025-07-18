"""
微信群聊天记录提取、分析和可视化工具

功能描述:
利用Gemini API自动获取、分析微信群聊记录并生成美观的HTML日报，帮助群成员快速了解群内重要信息与讨论内容。

使用方法:
python demo.py --talker "群名称" --days 0 --api-key "你的Gemini API密钥" --open-browser

参数说明:  （不填则默认从cfg.py读取，更稳定更省事、但不如CLI传参灵活）
--talker: 微信群名称
--days: 获取最近几天的聊天记录 (0表示仅当天，1表示今天和昨天)
--api-key: Gemini API密钥
--open-browser: 生成HTML后自动在浏览器中打开
--start-date: 自定义起始日期 (格式: YYYY-MM-DD)
--end-date: 自定义结束日期 (格式: YYYY-MM-DD)
--output-dir: 指定输出目录 (默认: ./output)
--prompt-path: 自定义Prompt模板路径 (默认: ./prompt_template.txt)

依赖安装:
pip install google-generativeai tqdm requests selenium webdriver-manager

作者: AI助手
版本: 1.2
"""

import requests
import subprocess
import time
import argparse
import logging
import sys
import webbrowser
from datetime import datetime, timedelta
import google.generativeai as genai
import tqdm  # 添加tqdm库用于显示进度条
import tkinter as tk
from tkinter import messagebox  # 弹窗，用于提示
import json
import os.path

# 添加HTML转PNG所需的依赖
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
from cfg import CHAT_DEMO_CFG

import os


# 创建日志目录
log_dir = CHAT_DEMO_CFG.get('log_dir', './logs')
os.makedirs(log_dir, exist_ok=True)

# 获取当前时间作为日志文件名
log_filename = f"{log_dir}/error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log.txt"

# 配置日志
logging.basicConfig(
    level=getattr(logging, CHAT_DEMO_CFG.get('logging_level', 'INFO')),
    format=CHAT_DEMO_CFG.get(
        'logging_format', '%(asctime)s - %(levelname)s - %(message)s'),
    datefmt=CHAT_DEMO_CFG.get('logging_date_format', '%Y-%m-%d %H:%M:%S')
)
logger = logging.getLogger(__name__)

# 添加文件处理器，只记录ERROR级别的日志
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.ERROR)
file_formatter = logging.Formatter(CHAT_DEMO_CFG.get(
    'logging_format', '%(asctime)s - %(levelname)s - %(message)s'))
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

base_server_ip_port = CHAT_DEMO_CFG.get(
    'chatlog_server_ip_port', "127.0.0.1:5036")
base_server_url = CHAT_DEMO_CFG.get(
    'chatlog_server_url', f"http://{base_server_ip_port}")

TPM_errorFix = {
    "token_ratio": 0.9,  # 减少token贴近【边界极值】的情况
    "sec_ratio": 1.2,  # 增长等待时间
}

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='微信群聊天记录提取、分析和可视化工具')

    parser.add_argument('--talker', type=str, help='微信群名称')
    parser.add_argument('--days', type=int,
                        help='获取最近多少天的聊天记录。当填写为0时，代表就只是当天。填写为1时，代表今天和昨天。')
    parser.add_argument('--api-key', type=str, help='Google Gemini API密钥')
    parser.add_argument('--output-dir', type=str,
                        default=CHAT_DEMO_CFG.get('output_dir', './output'), help='输出目录')
    parser.add_argument('--prompt-path', type=str,
                        default=CHAT_DEMO_CFG.get('prompt_template_path', './prompt_template.txt'), help='Prompt模板路径')
    parser.add_argument('--open-browser', action='store_true',
                        help='生成HTML后自动在浏览器中打开')
    parser.add_argument('--start-date', type=str, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--generate-png', action='store_true',
                        help='生成HTML后转换为PNG图片')
    parser.add_argument('--generate-url', action='store_true',
                        help='生成HTML后发布成URL')
    parser.add_argument('--hosting-address', type=str,
                        help='托管网站地址')
    parser.add_argument('--requires-password', action='store_true',
                        help='发布URL是否需要密码')
    parser.add_argument('--auto-mode', action='store_true',
                        help='自动模式，不需要用户交互')

    return parser.parse_args()


def load_config_from_json():
    return CHAT_DEMO_CFG

def init_gemini_api(api_key):
    """初始化Gemini API"""
    try:
        genai.configure(api_key=api_key)

        # gemini-2.5-pro-preview-03-25 available for free (this an update of gemini-2.5-pro-exp-03-25) : r/LocalLLaMA    https://www.reddit.com/r/LocalLLaMA/comments/1jrwstn/gemini25propreview0325_available_for_free_this_an/
        # 'gemini-2.5-pro-preview-03-25'  # 是【gemini-2.5-pro-exp-03-25】的升级版。但是要收费。
        # 'gemini-2.5-pro-preview-05-06',
        # 'gemini-2.5-pro-exp-03-25'  # 这个是免费的。
        # 'gemini-2.5-flash-preview-04-17',
        model_name = 'models/gemini-2.5-flash-preview-05-20'  # 默认模型
        selected_model_info = None

        # 模型 TPM 配置 (Tokens Per Minute)
        MODEL_CONFIG = {
            'models/gemini-2.5-flash-preview-05-20': {
                # "name": 'models/gemini-2.5-flash-preview-04-17-thinking',
                "tpm": 250000,
            },
            # 'models/gemini-1.5-flash-latest': 250000, # 假设值，请根据实际情况调整
            # 'models/gemini-1.5-pro-latest': 1000000, # 假设值
            # 可以根据需要添加更多模型的TPM配置
        }
        tpm_limit = MODEL_CONFIG.get(model_name).get("tpm") * (TPM_errorFix["token_ratio"])  # 默认 TPM 或从配置读取

        # print("可用模型列表:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")
                if m.name == model_name:  # 选择我们想要使用的模型
                    selected_model_info = m

        if not selected_model_info:
            # 如果默认模型不可用，尝试选择第一个可用的
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    model_name = m.name
                    selected_model_info = m
                    logger.warning(f"默认模型 {model_name} 未找到或不可用，已自动选择第一个可用模型: {model_name}")
                    break
            if not selected_model_info:
                raise Exception("未找到任何可用的 Gemini 模型。")

        model = genai.GenerativeModel(model_name)

        input_token_limit = selected_model_info.input_token_limit
        output_token_limit = selected_model_info.output_token_limit

        logger.info(f"成功连接到Gemini API，使用模型: {model_name}")
        logger.info(f"模型输入 Token 限制: {input_token_limit}")
        logger.info(f"模型输出 Token 限制: {output_token_limit}")
        logger.info(f"模型 TPM (Tokens Per Minute) 限制: {tpm_limit}")
        # print(f"DEBUG: Selected model info: {selected_model_info}")

        return model, model_name, input_token_limit, output_token_limit, tpm_limit
    except Exception as e:
        logger.error(f"初始化Gemini API失败: {str(e)}")
        print("此为常见问题：根源在海外接口无法联通，请考虑全局proxy上网等选项。")
        raise

wait_sec = CHAT_DEMO_CFG.get('manual_gui_auto_decryption_wait_sec', 30)


def alert_msg():
    """显示阻塞型对话框，并等待用户确认"""
    # 检查是否为自动模式
    args = parse_arguments()

    # 尝试从配置文件加载配置
    config = load_config_from_json()

    # 如果命令行没有传入auto_mode（即为False），则从配置文件中获取
    if not args.auto_mode:
        args.auto_mode = config.get('auto_mode', False)  # 默认为False，如果cfg中也没有
        logger.info(f"从配置文件加载 auto_mode: {args.auto_mode}")

    if args.auto_mode:
        logger.info("自动模式：跳过用户交互，继续执行...")
        print("自动模式：跳过用户交互，继续执行...")
        time.sleep(wait_sec)  # 仍然等待指定的时间
        return
        
    try:
        print("正在创建提示对话框...")

        # 用于跟踪用户是否正常点击了确认按钮
        user_confirmed = False

        # 创建Tk根窗口
        root = tk.Tk()
        root.title("操作提示")
        # 设置窗口大小和位置
        root.geometry("500x200")
        # 确保窗口在最上层显示
        root.attributes('-topmost', True)

        # 创建对话框内容
        frame = tk.Frame(root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        msg_label = tk.Label(
            frame,
            text="因源chatlog项目代码限制（v0.0.15），自动解密功能仅对GUI版本开放。\n\n"
                 "请您在GUI窗口中，点击【开启自动解密】\n"
                 "（如显示【停止自动解密】，说明已处于开启状态，不需要再次点击）",
            wraplength=450,
            justify=tk.LEFT
        )
        msg_label.pack(pady=10)

        # 添加自定义按钮
        def on_close():
            nonlocal user_confirmed
            print("用户点击了确认按钮，对话框即将关闭...")
            user_confirmed = True
            root.destroy()

        ok_button = tk.Button(
            frame,
            text=f"我已处于开启状态，继续\n（后续会等待{wait_sec}秒，等待数据同步完成）",
            width=50,
            height=3,
            command=on_close
        )
        ok_button.pack(pady=10)

        # 处理窗口关闭事件
        def on_window_close():
            nonlocal user_confirmed
            if not user_confirmed:
                print("警告：用户通过右上角关闭了窗口而不是点击确认按钮！")
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_window_close)

        # 确保对话框居中显示
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        print("对话框准备完成，开始显示...")
        # 开始主循环
        root.mainloop()
        print("对话框已关闭")

        # 如果用户没有通过按钮确认，而是关闭了窗口，则抛出异常
        if not user_confirmed:
            raise Exception("用户通过关闭窗口取消了操作，程序终止")

    except Exception as e:
        print(f"对话框操作出错: {str(e)}")
        logging.error(f"对话框操作出错: {str(e)}")
        # 重新抛出异常，确保调用者知道操作被取消
        raise Exception(f"对话框操作被取消: {str(e)}")


def run_chatlog_commands():
    """运行chatlog命令启动服务器"""
    try:
        # 从配置中获取chatlog可执行文件路径
        chatlog_exe = CHAT_DEMO_CFG.get(
            'chatlog_exe_path', "D:/Program_Files/ChatLog/chatlog.exe")
        wx_version = CHAT_DEMO_CFG.get('wx_version', "4")

        # 获取微信数据密钥
        logger.info("获取微信数据密钥...")
        key_process = subprocess.run(
            [chatlog_exe, "key"], capture_output=True, text=True, check=True)
        key = key_process.stdout.strip()
        # print(key)

        # 解密数据库文件
        logger.info("解密数据库文件...")

        subprocess.run([
            chatlog_exe, "decrypt",
            "--data-dir", CHAT_DEMO_CFG.get('wechat_data_dir'),
            "--key", key,
            "--version", wx_version,
        ], check=True)

        # 如果启用了手动GUI解密选项，则启动GUI并显示阻塞型弹窗
        if CHAT_DEMO_CFG.get('manual_gui_auto_decryption', False):
            # 此处，如果没有新开窗口的话，则需要：——————>（请注意，如无新开窗口，应该在【命令行】 而非PyCharm的【Run运行】中启动，后者会处于等待状态）
            logger.info("正在启动GUI...")

            # 启动GUI程序（在新的终端窗口中）
            if sys.platform == 'win32':
                # 获取完整路径
                chatlog_exe_abs_path = os.path.abspath(chatlog_exe)

                # 确保temp目录存在
                temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
                os.makedirs(temp_dir, exist_ok=True)

                # 创建批处理文件
                # 创建批处理文件临时执行，避免命令行引号嵌套问题
                batch_file = os.path.join(temp_dir, "run_chatlog_temp.bat")
                # batch_file = os.path.join(os.path.dirname(__file__), 'temp', "run_chatlog_temp.bat")

                with open(batch_file, "w") as f:
                    f.write(f'@echo off\n"{chatlog_exe_abs_path}"\npause')
                # 执行批处理文件
                subprocess.Popen(f'start cmd /c "{batch_file}"', shell=True)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', '-a', 'Terminal', chatlog_exe])
            else:  # Linux
                subprocess.Popen(['gnome-terminal', '--', chatlog_exe])

            logger.info("产生一个提示，并阻塞等待交互...")

            # 等待一会儿让GUI程序启动
            time.sleep(1)

            # 显示提示对话框并处理可能的异常
            try:
                logger.info("显示操作提示对话框...")
                alert_msg()
                logger.info("用户确认GUI操作完成")
                # 添加倒计时进度条
                print(f"等待数据同步完成，倒计时 {wait_sec} 秒...")
                with tqdm.tqdm(total=wait_sec, desc="数据同步（同步完后可关闭chatlog的GUI窗口）", unit="秒", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
                    for _ in range(wait_sec):
                        time.sleep(1)
                        pbar.update(1)
                print("数据同步等待完成")
            except Exception as e:
                logger.error(f"用户取消了操作: {str(e)}")
                raise Exception(f"用户取消了GUI操作，程序终止: {str(e)}")

        test_alive_api = base_server_url + "/api/v1/chatroom"

        # 检查服务器是否已经在运行
        try:
            requests.get(test_alive_api, timeout=2)
            logger.info("Chatlog服务器已经在运行")
            return None
        except requests.exceptions.RequestException as e:
            print(str(e))
            logger.info("启动新的Chatlog服务器...")

        # 启动HTTP服务器
        server_process = subprocess.Popen([
            chatlog_exe, "server",
            "--addr", base_server_ip_port,
            "--data-dir", CHAT_DEMO_CFG.get('wechat_data_dir'),
            "--work-dir", CHAT_DEMO_CFG.get('chatlog_work_dir'),
            "--platform", "windows",
            "--version", wx_version,
        ])

        # 等待服务器启动
        logger.info("等待服务器启动...")

        def wait_for_server_startup():
            """等待服务器启动并确认可以访问"""
            max_retries = 10
            retry_interval = 1
            for i in range(max_retries):
                try:
                    response = requests.get(
                        test_alive_api, timeout=2)
                    if response.status_code == 200 and response.text:
                        logger.info("服务器启动成功，已确认可以访问聊天室数据")
                        return
                    else:
                        logger.warning(
                            f"服务器响应但未返回数据，等待重试 ({i + 1}/{max_retries})...")
                except requests.exceptions.RequestException as e:
                    print(str(e))
                    logger.info(f"等待服务器启动中 ({i + 1}/{max_retries})...")
                time.sleep(retry_interval)

            # 多次重试后仍未成功启动，抛出异常
            raise Exception("服务器启动失败，无法访问聊天室数据", test_alive_api)

        wait_for_server_startup()
        return server_process
    except Exception as e:
        logger.error(f"运行chatlog命令失败: {str(e)}")
        raise


def get_chat_logs(talker_name, days, start_date=None, end_date=None, ):
    """获取指定群的聊天记录"""
    try:
        # 计算日期范围
        if end_date is None:
            # 设置为当前日期
            end_date_obj = datetime.now()
            end_date_obj = end_date_obj + timedelta(
                # 之前以为的Bug：加1天以符合左闭右开区间——————>后来发现，应该是【3.x】没获得数据，仅此而已。
                # days=1
                days=0
            )
            end_date = end_date_obj.strftime("%Y-%m-%d")
        else:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
                # days=1             # 如果end_date已提供，也需要加1天
                days=0  # 后来发现，0天就行。并不是这个的bug。
            )
            end_date = end_date_obj.strftime("%Y-%m-%d")

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=days)
                          ).strftime("%Y-%m-%d")

        logger.info(f"获取群'{talker_name}'从{start_date}到{end_date}的聊天记录...")

        # noinspection PyUnresolvedReferences
        # URL编码群名称
        encoded_talker_name = requests.utils.quote(talker_name)

        # 构建API URL
        url = f"{base_server_url}/api/v1/chatlog?time={start_date}~{end_date}&talker={encoded_talker_name}"

        # 发送GET请求
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            chat_logs = response.text
            if not chat_logs:
                logger.warning("获取到的聊天记录为空。可能是群不存在或在指定时间范围内没有消息。")
            else:
                logger.info(f"成功获取聊天记录: {len(chat_logs)}字符")

                # 应用数据打码规则
                data_masking_rules = CHAT_DEMO_CFG.get('data_masking_rules', {})
                if data_masking_rules:
                    logger.info(f"开始应用数据打码规则，共 {len(data_masking_rules)} 条规则...")
                    for keyword, replacement in data_masking_rules.items():
                        chat_logs = chat_logs.replace(keyword, replacement)
                    logger.info(f"数据打码完成，处理后聊天记录长度: {len(chat_logs)}字符")
                else:
                    logger.info("未配置数据打码规则，跳过处理。")
            return chat_logs
        else:
            error_msg = f"获取聊天记录失败: {response.status_code}, {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
    except Exception as e:
        logger.error(f"获取聊天记录时出错: {str(e)}")
        raise


def read_prompt_template(template_path):
    """读取Prompt模板文件"""
    try:
        logger.info(f"从{template_path}读取prompt模板")
        with open(template_path, 'r', encoding='utf-8') as file:
            template = file.read()

        if not template:
            raise ValueError("Prompt模板文件为空")

        logger.info(f"成功读取prompt模板: {len(template)}字符")
        return template
    except Exception as e:
        logger.error(f"读取prompt模板失败: {str(e)}")
        raise


def split_chat_logs_into_segments(model, base_prompt_fixed_parts_text, chat_logs_text, model_input_token_limit, tpm_limit):
    """
    将聊天记录分割成适合模型输入长度的片段。

    Args:
        model: Gemini 模型实例。
        base_prompt_fixed_parts_text: 基础prompt中除了聊天记录本身之外的固定文本内容。
        chat_logs_text: 完整的聊天记录文本。
        model_input_token_limit: 模型允许的总输入token数。
        tpm_limit: 模型 TPM (Tokens Per Minute) 限制。

    Returns:
        list: 聊天记录片段的列表。
    """
    SAFETY_MARGIN_TOKENS = CHAT_DEMO_CFG.get('safety_margin_tokens', 1000)  # 安全边际，防止精确达到上限

    try:
        logger.info("正在计算基础Prompt的Token数...")  # 增加日志
        base_prompt_start_time = time.time()
        base_prompt_tokens = model.count_tokens(base_prompt_fixed_parts_text).total_tokens
        base_prompt_end_time = time.time()
        logger.info(f"基础Prompt部分的Token数: {base_prompt_tokens} (计算耗时: {base_prompt_end_time - base_prompt_start_time:.4f} 秒)")
    except Exception as e:
        logger.error(f"计算基础Prompt Token数时出错: {e}. 使用默认值0.")
        base_prompt_tokens = 0  # 容错处理

    # 确定单个请求的最大允许Token数，考虑模型输入限制和TPM限制
    # 注意：这里的 token 限制是针对整个 prompt (基础 prompt + 聊天记录片段)
    effective_max_prompt_tokens = min(model_input_token_limit, tpm_limit)
    logger.info(f"分片时生效的单次请求最大Token数 (min(model_input_limit, tpm_limit)): {effective_max_prompt_tokens}")

    # 为聊天记录本身留出的最大token数
    max_tokens_for_chat_log_segment = effective_max_prompt_tokens - base_prompt_tokens - SAFETY_MARGIN_TOKENS
    logger.info(f"每个聊天记录片段允许的最大Token数 (已减去基础Prompt和安全边际): {max_tokens_for_chat_log_segment}")

    if max_tokens_for_chat_log_segment <= 0:
        logger.error(f"计算得到的聊天记录片段允许的Token数 ({max_tokens_for_chat_log_segment}) 过小或为负。这可能是因为基础Prompt过长或安全边际设置过大。")
        # 强制至少允许少量token，避免除零或负数问题，但这很可能仍然会导致后续错误
        max_tokens_for_chat_log_segment = 100
        logger.warning(f"已将聊天记录片段允许的最大Token数强制设置为 {max_tokens_for_chat_log_segment} 以尝试继续。")

    # ==== 优化：尝试将整个聊天记录作为单个片段处理 ====
    try:
        logger.info("正在尝试计算整个聊天记录的Token总数...")
        overall_token_count_start_time = time.time()
        if not chat_logs_text:  # 确保 chat_logs_text 不为空
            logger.info("聊天记录为空，无需切分，返回空列表。")
            return []

        total_chat_log_tokens = model.count_tokens(chat_logs_text).total_tokens
        overall_token_count_end_time = time.time()
        logger.info(f"整个聊天记录的Token总数: {total_chat_log_tokens} (计算耗时: {overall_token_count_end_time - overall_token_count_start_time:.4f} 秒)")

        if total_chat_log_tokens <= max_tokens_for_chat_log_segment:
            logger.info(f"整个聊天记录 ({total_chat_log_tokens} tokens) 小于或等于允许的最大片段Token数 ({max_tokens_for_chat_log_segment}). 将其作为单个片段处理。")
            return [chat_logs_text]
        else:
            logger.info(f"整个聊天记录 ({total_chat_log_tokens} tokens) 大于允许的最大片段Token数 ({max_tokens_for_chat_log_segment}). 需要进行切分。")

    except Exception as e:
        logger.error(f"计算整个聊天记录Token数时出错: {e}. 将继续进行切分逻辑。")
    # ==== 优化结束 ====

    # ---- 如果整体日志过大，则使用二分法进行分片 ----
    logger.info("由于整个日志过大或初步Token计算失败，开始使用二分法进行智能分片...")
    segments = []
    all_lines = chat_logs_text.splitlines(keepends=True)
    current_pos = 0  # 当前处理到的起始行索引
    total_lines_count = len(all_lines)

    segment_creation_loop_start_time = time.time()
    segment_count = 0

    while current_pos < total_lines_count:
        segment_count += 1
        logger.info(f"开始为第 {segment_count} 个片段寻找最佳行数 (从第 {current_pos + 1} 行开始)...总行数 {total_lines_count}")

        # 二分搜索的范围是 [1, total_lines_count - current_pos]
        low = 1
        high = total_lines_count - current_pos
        best_k_for_segment = 0  # 本次二分查找到的最佳行数

        # 在二分查找前，先检查剩余所有行是否能直接放入一个片段 (可能在之前整体检查失败，但剩余部分较小)
        # This check is somewhat redundant if the overall check passed, but useful if it failed for other reasons
        # or if we want to be absolutely sure for the remainder.
        # For simplicity and performance, let's rely on the binary search to find the largest possible chunk.

        binary_search_start_time = time.time()
        iterations = 0
        while low <= high:
            iterations += 1
            mid_k = low + (high - low) // 2
            if mid_k == 0:  # 防止 mid_k 变为0导致死循环或切片错误
                break

            segment_text_to_test = "".join(all_lines[current_pos: current_pos + mid_k])
            try:
                tokens = model.count_tokens(segment_text_to_test).total_tokens
                if tokens <= max_tokens_for_chat_log_segment:
                    best_k_for_segment = mid_k  # 这是一个可行的k，尝试更大的k
                    low = mid_k + 1
                else:
                    high = mid_k - 1  # k太大了，减小k
            except Exception as e:
                logger.error(f"二分查找中计算 {mid_k} 行的Token数时出错 (行范围: {current_pos + 1}-{current_pos + mid_k}): {e}. 尝试减小行数。")
                high = mid_k - 1  # 假设出错的块过大或无效

        binary_search_duration = time.time() - binary_search_start_time
        logger.info(f"片段 {segment_count} 的二分查找完成: {iterations} 次迭代, 耗时 {binary_search_duration:.4f} 秒.")

        if best_k_for_segment > 0:
            actual_segment_text = "".join(all_lines[current_pos: current_pos + best_k_for_segment])
            segments.append(actual_segment_text)
            logger.info(f"创建片段 {segment_count}: 包含 {best_k_for_segment} 行 (从 {current_pos + 1} 到 {current_pos + best_k_for_segment}), Token数计算应已达标。")
            current_pos += best_k_for_segment
        else:
            # 如果 best_k_for_segment 为 0, 说明即使是第一行 (k=1) 也超限或出错
            logger.warning(f"无法为片段 {segment_count} 找到合适的行数（即使一行也可能超限或出错）。将尝试添加从 {current_pos + 1} 开始的第一行作为单独片段。")
            if current_pos < total_lines_count:  # 确保还有行可加
                single_line_segment = all_lines[current_pos]
                segments.append(single_line_segment)
                try:
                    sl_tokens = model.count_tokens(single_line_segment).total_tokens
                    logger.info(f"片段 {segment_count} (单行): 第 {current_pos + 1} 行, 字符数 {len(single_line_segment)}, Token数 {sl_tokens}. (可能超限)")
                except Exception as e_sl:
                    logger.warning(f"片段 {segment_count} (单行): 第 {current_pos + 1} 行, 字符数 {len(single_line_segment)}. Token计数失败: {e_sl}")
                current_pos += 1
            else:
                logger.error("已无更多行可处理，但未能正确切分。这不应发生。")
                break  # 避免死循环

    segment_creation_loop_duration = time.time() - segment_creation_loop_start_time
    logger.info(f"二分法分片完成。总共创建 {len(segments)} 个片段。总耗时: {segment_creation_loop_duration:.4f} 秒。")
    return segments


def build_complete_prompt(prompt_template, chat_logs, talker):
    """构建发送给Gemini的完整Prompt"""
    logger.info("构建完整prompt...")

    if not chat_logs:
        raise ValueError("聊天记录为空，无法构建prompt")

    complete_prompt = f"""你好，此处的txt为我的【群日报生成要求prompt】，另一外一份txt为我的【群聊记录】。

请你根据最新的群聊记录，按照prompt要求，生成一份群日报。要求仅返回html，不要返回其他内容。

【群聊名称】：
{talker}

【群日报生成要求prompt】：
{prompt_template}

【群聊记录】：
{chat_logs}

谢谢"""
    logger.info(f"完整prompt已构建: {len(complete_prompt)}字符")
    return complete_prompt


def extract_html_from_response(response_text):
    """从Gemini API的响应文本中提取HTML内容"""
    # 如果已经是HTML，直接返回
    if response_text.strip().startswith('<'):
        return response_text

    # 尝试从代码块中提取HTML
    if '```html' in response_text and '```' in response_text.split('```html', 1)[1]:
        html_content = response_text.split(
            '```html', 1)[1].split('```', 1)[0].strip()
        return html_content

    # 尝试提取<html>标签内容
    if '<html' in response_text and '</html>' in response_text:
        start_idx = response_text.find('<html')
        end_idx = response_text.find('</html>') + 7
        html_content = response_text[start_idx:end_idx]
        return html_content

    # 如果无法提取HTML，抛出异常
    err_msg = "无法从响应中提取HTML，原始文本内容如下（最多显示100字符）：\n" + response_text[:100]
    logger.error(err_msg)
    raise ValueError(err_msg)


def generate_html_with_gemini(model, prompt, tpm_limit, last_request_state):
    """使用Gemini API生成HTML内容，包含重试机制"""
    max_retries = CHAT_DEMO_CFG.get('gemini_retry_attempts', 3)
    retry_delay = CHAT_DEMO_CFG.get('gemini_retry_delay_sec', 10)
    attempts = 0

    while attempts < max_retries:
        try:
            # 计算当前prompt的token数
            current_prompt_tokens = 0
            try:
                count_tokens_result = model.count_tokens(prompt)
                current_prompt_tokens = count_tokens_result.total_tokens
                logger.info(f"当前请求的Prompt Token数: {current_prompt_tokens}")
            except Exception as e_count:
                logger.error(f"计算Prompt Token数失败: {str(e_count)}. 无法执行TPM检查，将直接发送请求。")
                # 如果无法计算token，为避免阻塞，不执行等待逻辑，但后续TPM可能仍会超限

            # TPM控制逻辑
            if current_prompt_tokens > 0 and last_request_state['start_time'] is not None:
                current_time = time.time()
                time_since_last_request = current_time - last_request_state['start_time']

                TPM_best_sec = (60 * TPM_errorFix["sec_ratio"])  # 增加容错，减少错误重试次数（变相节省时间）
                # 检查是否在1分钟内，并且组合token数超过TPM
                if time_since_last_request < TPM_best_sec:
                    combined_tokens = last_request_state['tokens'] + current_prompt_tokens
                    if combined_tokens > tpm_limit:
                        wait_duration = TPM_best_sec - time_since_last_request
                        logger.warning(
                            f"TPM限制可能超额 ({last_request_state['tokens']} + {current_prompt_tokens} = {combined_tokens} > {tpm_limit}). "
                            f"等待 {wait_duration:.2f} 秒..."
                        )
                        print(f"⏳ 为满足TPM限制，程序将暂停 {wait_duration:.2f} 秒...")
                        sys.stdout.flush()
                        time.sleep(wait_duration)
                        # 等待后，重置上一次请求状态，因为现在相当于一个新的分钟窗口的开始
                        # 或者说，我们认为等待后，之前那个请求的影响已经过去了
                        last_request_state['start_time'] = None
                        last_request_state['tokens'] = 0
                else:
                    # 如果距离上次请求超过1分钟，则之前的请求不再计入当前分钟的TPM额度
                    # 因此，我们将 last_request_state['tokens'] 视为0，或者说，我们只关心当前请求是否会触发等待
                    # （这里我们不需要做什么，因为如果 combined_tokens 检查不满足，就不会等待）
                    pass  # 实际上，如果超过1分钟，last_request_state['tokens'] 对 combined_tokens 的影响会消失

            print("""
                调试1 （有时会卡在这里，丢失后续的 logger.info 输出？）
                经过分析，应该是【flush缓冲区】、以及【print 和 logger.info】的乱序问题（这个倒经常出现）
                一般来说，稍微等待一会儿，即可""".strip())
            sys.stdout.flush()
            logger.info("向Gemini API发送prompt...")
            sys.stdout.flush()
            # 设置生成参数
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                # "max_output_tokens": 8192,
                "max_output_tokens": 65536,
            }

            # 发送请求到Gemini
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                stream=True,  # 流式传输
            )

            # 请求发送成功后，更新上一次请求的状态
            if current_prompt_tokens > 0:  # 仅当成功计算token时更新
                last_request_state['start_time'] = time.time()  # 记录本次请求的开始时间 (或结束时间)
                last_request_state['tokens'] = current_prompt_tokens
                logger.info(f"更新TPM状态: last_request_start_time={last_request_state['start_time']}, last_request_tokens={last_request_state['tokens']}")

            # 处理流式响应
            print("正在生成日报内容，请稍候...")
            sys.stdout.flush()
            response_text = ""
            # 创建一个动态进度条
            progress_bar = tqdm.tqdm(desc="生成进度", unit="字符", dynamic_ncols=True)

            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    current_chunk = chunk.text
                    response_text += current_chunk
                    # 更新进度条
                    progress_bar.update(len(current_chunk))
                    # 可选：每接收到一个块后显示最新的少量文本
                    if len(current_chunk) > 0 and len(current_chunk) < 100:
                        # 显示最近添加的文本片段，但避免输出HTML标签
                        readable_chunk = current_chunk.replace(
                            '<', '＜').replace('>', '＞')
                        progress_bar.set_description(
                            f"最新内容: {readable_chunk[:30]}...")

            # 关闭进度条
            progress_bar.close()
            print(f"内容生成完毕！共 {len(response_text)} 个字符")
            sys.stdout.flush()

            # 提取HTML内容
            html_content = extract_html_from_response(response_text)

            # 验证HTML基本结构
            if not ('<html' in html_content.lower() and '</html>' in html_content.lower()):
                logger.warning("生成的内容可能不是有效的HTML")

            logger.info(f"成功生成HTML内容: {len(html_content)}字符")
            return html_content  # 成功获取响应，跳出重试循环并返回结果

        except Exception as e:
            attempts += 1
            logger.error(f"使用Gemini生成HTML失败 (尝试 {attempts}/{max_retries}): {str(e)}")
            if attempts < max_retries:
                logger.info(f"将在 {retry_delay} 秒后重试...")
                print(f"⚠️ Gemini API请求失败，将在 {retry_delay} 秒后重试 ({attempts}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                logger.error(f"已达到最大重试次数 ({max_retries})，Gemini API调用最终失败。错误: {str(e)}")
                raise  # 重试次数耗尽，重新引发最后一个异常
    # 如果循环结束仍未成功（理论上不会到这里，因为要么return要么raise）
    logger.error("Gemini API调用在所有重试后均失败，且未正确抛出异常。")
    raise Exception("Gemini API调用在所有重试后均失败。")

def save_report_urls_to_unified_file(reports_info):
    """
    将所有群日报的URL和PNG地址保存到统一的txt文件中
    
    Args:
        reports_info: 包含所有群日报信息的列表，每个元素是一个字典，包含群名称、HTML文件路径、URL和PNG路径
    """
    try:
        # 获取当前日期作为文件名的一部分
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 创建输出目录（如果不存在）
        output_dir = os.path.join(CHAT_DEMO_CFG.get('output_dir', './output'), current_date)
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建统一的URL记录文件
        urls_file = os.path.join(output_dir, f"all_reports_urls_{current_date}.txt")
        
        # 准备写入的内容
        content = f"===== 群日报发布信息汇总 ({current_date}) =====\n\n"
        content += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 添加每个群日报的信息
        for i, report in enumerate(reports_info, 1):
            content += f"--- 群日报 #{i} ---\n"
            content += f"群聊名称: {report['talker']}\n"
            content += f"HTML文件: {os.path.abspath(report['html_filepath'])}\n"
            
            if report.get('html_url'):
                content += f"发布地址(URL): {report['html_url']}\n"
            
            if report.get('png_filepath'):
                content += f"PNG图片地址: {os.path.abspath(report['png_filepath'])}\n"
            
            content += "\n"
            
        # 写入文件
        # 检查文件是否存在，如果存在则添加分隔线
        file_exists = os.path.exists(urls_file) and os.path.getsize(urls_file) > 0
        with open(urls_file, "a", encoding="utf-8") as f:
            # 如果文件已存在且非空，添加分隔线
            if file_exists:
                f.write("\n\n==================== 新增群日报发布信息 =========================\n\n")
            f.write(content)
            
        logger.info(f"已保存所有群日报URL信息到: {urls_file}")
        print(f"✅ 所有群日报URL信息已保存至: {urls_file}")
        
        return urls_file
        
    except Exception as e:
        logger.error(f"保存群日报URL信息失败: {str(e)}")
        print(f"❌ 保存群日报URL信息失败: {str(e)}")
        return None

def save_html(html_content, output_dir, talker_name, related_link=None):
    """保存HTML文件"""
    try:
        # 当前日期作为目录名
        date_folder = datetime.now().strftime("%Y-%m-%d")
        output_subdir = os.path.join(output_dir, date_folder)

        # 确保输出目录存在
        os.makedirs(output_subdir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{talker_name}_群日报_{timestamp}.html"
        filepath = os.path.join(output_subdir, filename)

        logger.info(f"保存HTML至: {filepath}")
        
        # 优先使用传入的related_link，如果没有则使用全局配置
        if related_link is None:
            related_link = CHAT_DEMO_CFG.get('related_link', {})
        
        logger.info(f"使用的related_link配置: {related_link}")
            
        # 添加footer关联链接
        if related_link:
            link_text = related_link.get('text', '查看更多群日报')
            link_url = related_link.get('url', '#')
            footer_html = f'<footer style="text-align: center; margin-top: 30px; padding: 10px; border-top: 1px solid #eee;">' 
            footer_html += f'<a href="{link_url}" target="_blank">{link_text}</a>'
            footer_html += f'</footer>'
            
            # 替换HTML结尾标签
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', footer_html + '</body>')
            elif '</html>' in html_content:
                html_content = html_content.replace('</html>', footer_html + '</html>')
            else:
                html_content += footer_html
        
        # 写入HTML文件
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(html_content)

        logger.info(f"成功保存HTML文件: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"保存HTML文件失败: {str(e)}")
        raise

def html_to_png(html_filepath):
    """将HTML文件转换为PNG图片 便于分享
    toDo 后续可根据系统判断使用怎样方式进行截图

    Args:
        html_filepath: HTML文件的完整路径

    Returns:
        png_filepath: 生成的PNG图片的完整路径
    """
    try:
        logger.info(f"开始将HTML转换为PNG: {html_filepath}")

        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")  # 设置窗口大小

        # 初始化WebDriver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # 加载HTML文件
        html_url = f"file:///{os.path.abspath(html_filepath)}"
        driver.get(html_url)

        # 等待页面加载完成
        time.sleep(2)

        # 获取页面实际高度
        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1920, page_height)

        # 再次等待以确保调整后的页面完全加载
        time.sleep(1)

        # 生成PNG文件路径
        png_filepath = os.path.splitext(html_filepath)[0] + ".png"

        # 截图并保存
        driver.save_screenshot(png_filepath)

        # 关闭WebDriver
        driver.quit()

        logger.info(f"HTML已成功转换为PNG: {png_filepath}")
        return png_filepath
    except Exception as e:
        logger.error(f"HTML转PNG失败: {str(e)}")
        print(f"HTML转PNG过程中出错: {str(e)}")
        return None


def upload_html_to_server(html_content, is_protected=False,
    server_url="http://localhost:8888"):
  """
  通过API上传HTML内容到服务器

  参数:
      html_content (str): 要上传的HTML内容
      is_protected (bool): 是否需要密码保护，默认为False
      server_url (str): 服务器URL，默认为http://localhost:8888

  返回:
      dict: 包含上传结果的字典，成功时包含urlId和password
  """
  # API端点
  api_endpoint = f"{server_url}/api/pages/create"

  # 请求头
  headers = {
    "Content-Type": "application/json"
  }

  # 请求数据
  payload = {
    "htmlContent": html_content,
    "isProtected": is_protected
  }

  try:
    # 使用会话发送POST请求
    response = requests.post(
        api_endpoint,
        headers=headers,
        json=payload  # 使用json参数自动处理JSON序列化
    )

    # 检查响应状态
    if response.status_code == 200:
      result = response.json()
      url = f"{server_url}/view/{result['urlId']}"
      if is_protected:
        url += f"?password={result['password']}"
      if result.get("success"):
        print(f"上传成功！URL ID: {result['urlId']}")
        print(f"密码: {result['password']}")
        print(f"访问链接: {server_url}/view/{result['urlId']}")
        return url
      else:
        print(f"上传失败: {result.get('error', '未知错误')}")
        return None
    else:
      print(f"请求：{server_url} 失败，状态码: {response.status_code}")
      return None
  except Exception as e:
    print(f"发生错误: {str(e)}")
    return None


def open_in_browser(html_filepath):
    """在默认浏览器中打开HTML文件"""
    try:
        logger.info(f"在浏览器中打开HTML文件: {html_filepath}")
        webbrowser.open(f"file://{os.path.abspath(html_filepath)}")
    except Exception as e:
        logger.error(f"在浏览器中打开文件失败: {str(e)}")


# 测试海外Google联通性。
def check_oversea_conn():
    import os

    # 如果您需要指定本机Proxy代理（如Clash、V2ray等），可以开启此开关（并修改IP、端口）。
    use_env_proxy = True
    if use_env_proxy:
        os.environ['http_proxy'] = 'http://127.0.0.1:7899'
        os.environ['https_proxy'] = 'http://127.0.0.1:7899'
        os.environ['all_proxy'] = 'socks5://127.0.0.1:7899'

    # 相关API文档测试
    resp____oversea_conn_test = requests.get("https://generativelanguage.googleapis.com/$discovery/rest")
    print("\n检查Google服务网络连接\n", resp____oversea_conn_test.text, '（此处【 "code": 403 、 200 】都属于正常）')


def main():
    check_oversea_conn()

    """主函数"""
    server_process = None

    try:
        # 解析命令行参数
        args = parse_arguments()

        print("-" * 50)
        print("🚀 微信群聊日报生成工具已启动")

        # 尝试从配置文件加载配置
        config = load_config_from_json()

        # 获取talkers列表
        talkers = []
        if args.talker:
            # 命令行参数提供的talker名称，创建一个简单的字典结构
            talkers = [{'name': args.talker}]
        elif 'talkers' in config and isinstance(config['talkers'], list):
            # 从配置文件加载talkers
            talkers = config['talkers']
            # 检查talkers列表中的元素是否为字典格式，如果不是，转换为字典格式
            for i, talker in enumerate(talkers):
                if isinstance(talker, str):
                    # 兼容旧格式：如果是字符串，转换为字典格式
                    talkers[i] = {'name': talker}
            logger.info(f"从配置文件加载talkers: {talkers}")

        if not talkers:
            raise ValueError(
                "必须提供至少一个talker名称，可通过--talker参数或在cfg.json中设置talkers数组")

        # 如果命令行没有传入days，则从配置文件中获取
        if args.days is None:
            args.days = config.get('days', 0) # 默认为0，如果cfg中也没有
            logger.info(f"从配置文件加载days: {args.days}")

        # 如果命令行没有传入auto_mode（即为False），则从配置文件中获取
        if not args.auto_mode:
            args.auto_mode = config.get('auto_mode', False) # 默认为False，如果cfg中也没有
            logger.info(f"从配置文件加载 auto_mode: {args.auto_mode}")
        else:
            logger.info(f"从命令行参数获取 auto_mode: {args.auto_mode}")


        # 显示目标群聊名称列表
        talker_names = [t['name'] for t in talkers]
        print(f"📊 目标群聊: {', '.join(talker_names)}")
        if args.start_date and args.end_date:
            print(f"📅 时间范围: {args.start_date} 至 {args.end_date}")
        else:
            print(f"📅 时间范围: 近 {args.days} 天")
            if args.days > 1:
                if not args.auto_mode:
                    messagebox.showinfo("友情提示", f"您的请求天数大于1（为{args.days}天），数据量较多的情况下，有可能日报会分为多个part输出")
                else:
                    logger.info("自动模式：跳过用户交互:友情提示...，继续执行...")
        print("-" * 50)

        # 检查API密钥
        if not args.api_key:
            args.api_key = config.get(
                'api_key') or os.environ.get('GEMINI_API_KEY')
            if not args.api_key:
                raise ValueError(
                    "必须提供Gemini API密钥，可通过--api-key参数、cfg.py配置文件或GEMINI_API_KEY环境变量设置")

        print("⏳ 启动数据服务中...")
        # 运行chatlog命令
        server_process = run_chatlog_commands()
        print("✅ 数据服务已启动")

        # 初始化Gemini API
        print("⏳ 连接AI服务中...")
        model, model_name, model_input_token_limit, model_output_token_limit, tpm_limit = init_gemini_api(args.api_key)
        print(f"✅ AI服务连接成功 (模型: {model_name}, 输入限制: {model_input_token_limit} tokens, 输出限制: {model_output_token_limit} tokens, TPM限制: {tpm_limit} tokens/min)")

        # 读取Prompt模板
        print("⏳ 正在加载日报模板...")
        prompt_template = read_prompt_template(args.prompt_path)
        print("✅ 模板加载完成")

        # 初始化TPM控制所需的状态变量
        last_request_state = {
            'start_time': None,  # 上一次请求的开始时间戳
            'tokens': 0  # 上一次请求的token数
        }

        # 创建一个列表来存储所有群日报的信息
        all_reports_info = []

        # 处理每个talker
        for talker_index, talker_config in enumerate(talkers):
            try:
                # 获取talker名称
                talker_name = talker_config['name']
                print(f"\n--- 开始处理 「{talker_name}」 ({talker_index + 1}/{len(talkers)}) ---")

                # 获取聊天记录
                print(f"⏳ 正在获取「{talker_name}」的聊天记录...")
                full_chat_logs = get_chat_logs(
                    talker_name,
                    args.days,
                    args.start_date,
                    args.end_date,
                )

                if not full_chat_logs:
                    print(f"❌ 未获取到「{talker_name}」的聊天记录，请检查群名称是否正确或时间范围内是否有消息")
                    logger.warning(f"未获取到「{talker_name}」的聊天记录，跳过。")
                    continue
                print(f"✅ 成功获取「{talker_name}」的完整聊天记录: {len(full_chat_logs)}字符")

                # 获取talker个性化的prompt模板路径
                talker_prompt_path = talker_config.get('prompt_template_path', args.prompt_path)
                # 如果talker配置了自己的prompt模板，则使用它
                if talker_prompt_path != args.prompt_path:
                    print(f"⏳ 正在加载「{talker_name}」的个性化日报模板...")
                    prompt_template = read_prompt_template(talker_prompt_path)
                    print(f"✅ 「{talker_name}」的个性化模板加载完成")

                # 确定基础Prompt的固定部分内容，用于计算token
                # 注意：这里的 chat_logs 参数用一个简短的占位符，或者为空字符串，
                # 因为我们只关心模板和其他固定文本的token数。
                # 关键是这里的结构要和 build_complete_prompt 函数内实际拼接时保持一致。
                base_prompt_fixed_parts_text = f"""你好，此处的txt为我的【群日报生成要求prompt】，另一外一份txt为我的【群聊记录】。

                    请你根据最新的群聊记录，按照prompt要求，生成一份群日报。要求仅返回html，不要返回其他内容。
                    
                    【群聊名称】：
                    {talker_name}
                    
                    【群日报生成要求prompt】：
                    {prompt_template}
                    
                    【群聊记录】：
                    
                    
                    谢谢
                    """

                # 切分聊天记录
                print(f"⏳ 正在为「{talker_name}」的聊天记录按Token数切片...")
                chat_log_segments = split_chat_logs_into_segments(
                    model,
                    base_prompt_fixed_parts_text,
                    full_chat_logs,
                    model_input_token_limit,
                    tpm_limit
                )

                if not chat_log_segments:
                    print(f"❌ 「{talker_name}」的聊天记录切片失败或为空，跳过此群聊。")
                    logger.warning(f"「{talker_name}」的聊天记录未能切分出任何片段，跳过。")
                    continue

                print(f"✅ 「{talker_name}」的聊天记录被切分为 {len(chat_log_segments)} 个片段进行处理。")

                for segment_index, chat_segment in enumerate(chat_log_segments):
                    segment_display_name = f"{talker_name} (片段 {segment_index + 1}/{len(chat_log_segments)})"
                    print(f"\n  --- 开始处理 「{segment_display_name}」 ---")

                    if not chat_segment.strip():
                        print(f"⚪ 「{segment_display_name}」内容为空，跳过此片段。")
                        logger.info(f"「{segment_display_name}」内容为空，跳过。")
                        continue

                    # 构建完整的Prompt
                    print(f"  ⏳ 正在为「{segment_display_name}」准备AI分析数据...")
                    complete_prompt = build_complete_prompt(
                        prompt_template, chat_segment,  # 使用切分后的片段
                        talker=talker_name,
                    )
                    print(f"  ✅ 「{segment_display_name}」分析数据准备完成 (Prompt长度: {len(complete_prompt)}字符)")

                    # 使用Gemini生成HTML
                    print(f"  ⏳ 「{segment_display_name}」开始AI分析并生成日报...")
                    html_content = generate_html_with_gemini(
                        model,
                        complete_prompt,
                        tpm_limit,  # 新增TPM限制参数
                        last_request_state  # 新增请求状态参数 (会被修改)
                    )

                    # 获取talker个性化配置，如果没有则使用全局配置
                    auto_generate_png = talker_config.get('auto_generate_png', CHAT_DEMO_CFG.get('auto_generate_png', False))
                    auto_generate_url = talker_config.get('auto_generate_url', CHAT_DEMO_CFG.get('auto_generate_url', False))
                    url_requires_password = talker_config.get('url_requires_password', CHAT_DEMO_CFG.get('url_requires_password', False))
                    # 获取相关链接配置
                    related_link = talker_config.get('related_link', None)
                    
                    # 保存HTML文件，如果多片段，文件名包含片段号
                    print(f"  ⏳ 正在为「{segment_display_name}」保存日报文件...")
                    file_suffix = f"_part_{segment_index + 1}" if len(chat_log_segments) > 1 else ""
                    output_filename_base = f"{talker_name}{file_suffix}"

                    html_filepath = save_html(
                        html_content, args.output_dir, output_filename_base, related_link)
                    print(f"  ✅ 「{segment_display_name}」日报已保存至: {html_filepath}")

                    # 初始化变量
                    png_filepath = None
                    html_url = None
                    
                    # 将HTML转换为PNG图片
                    if auto_generate_png:
                        png_filepath = html_to_png(html_filepath)
                        if png_filepath:
                            print(f"✅ PNG图片已保存至: {png_filepath}")
                        else:
                            print("❌ PNG图片生成失败，请检查日志")

                    # 将HTML发布到托管服务器（前提部署了html托管服务）
                    if auto_generate_url:
                        # 获取边缘托管地址
                        hosting_address = CHAT_DEMO_CFG.get(
                            'website_hosting_address', "http://localhost:8888")
                        
                        # 读取已保存的HTML文件内容（包含footer）
                        with open(html_filepath, 'r', encoding='utf-8') as file:
                            html_content_with_footer = file.read()
                        
                        # 使用包含footer的HTML内容上传
                        html_url = upload_html_to_server(html_content_with_footer,
                                                         url_requires_password,
                                                         hosting_address)
                        if html_url:
                            print(f"✅ URL已生成: {html_url}")
                        else:
                            print("❌ URL生成失败，请检查日志")
                    
                    # 收集当前群日报的信息
                    report_info = {
                        'talker': talker_name,
                        'html_filepath': html_filepath,
                        'html_url': html_url,
                        'png_filepath': png_filepath,
                        'auto_send_to_wechat': talker_config.get('auto_send_to_wechat', CHAT_DEMO_CFG.get('auto_send_to_wechat', False)),
                        'wechat_message_prefix': talker_config.get('wechat_message_prefix', CHAT_DEMO_CFG.get('wechat_message_prefix', "今日群日报已生成：")),
                        'auto_sync_to_feishu': talker_config.get('auto_sync_to_feishu', CHAT_DEMO_CFG.get('auto_sync_to_feishu', False)),
                        'related_link': related_link
                    }
                    all_reports_info.append(report_info)

                    # 如果需要，在浏览器中打开HTML
                    open_browser = CHAT_DEMO_CFG.get('auto_open_browser', False)
                    if open_browser and html_filepath:
                        # 如果发布成功且配置了 URL，则打开 URL
                        if html_url:
                            print(
                                f"  ⏳ 正在为「{segment_display_name}」打开URL...")
                            webbrowser.open(html_url)
                            print(
                                f"  ✅ 已在浏览器中打开「{segment_display_name}」的日报")
                        else:
                          # 如果指定了，在浏览器中打开HTML文件
                            print(
                                f"  ⏳ 正在为「{segment_display_name}」打开浏览器...")
                            webbrowser.open(
                                f"file://{os.path.abspath(html_filepath)}")
                            print(
                                f"  ✅ 已在浏览器中打开「{segment_display_name}」的日报")

                    print(f"  --- 「{segment_display_name}」处理完成 ---")
            except Exception as e:
                print(f"\n❌ 处理「{talker_name}」时出错 (在片段处理中或之前): {str(e)}")
                logger.error(f"处理「{talker_name}」时出错: {str(e)}")
                continue

        # 所有群日报处理完成后，保存统一的URL记录文件
        if all_reports_info:
            urls_file = save_report_urls_to_unified_file(all_reports_info)
            if urls_file:
                print(f"✅ 所有群日报的URL信息已统一保存到: {urls_file}")
                
            # 自动发送URL到微信群
            try:
                from wx_sender import send_url_to_wechat_group
                
                print("\n--- 开始向微信群发送群日报URL ---")
                # 获取发送延迟时间
                delay = CHAT_DEMO_CFG.get('wechat_send_delay_seconds', 5)
                
                # 发送URL到对应群聊
                success_count = 0
                # 筛选需要发送到微信的报告
                valid_reports = [r for r in all_reports_info if r.get('html_url') and r.get('talker') and r.get('auto_send_to_wechat', False)]
                
                if not valid_reports:
                    print("没有需要发送到微信的群日报，跳过微信发送步骤。")
                else:
                    for report in valid_reports:
                        talker = report['talker']
                        url = report['html_url']
                        # 使用talker个性化的消息前缀
                        message_prefix = report.get('wechat_message_prefix', "今日群日报已生成：")
                        
                        print(f"⏳ 正在向群聊 '{talker}' 发送URL...")
                        if send_url_to_wechat_group(talker, url, message_prefix):
                            success_count += 1
                            print(f"✅ 成功向群聊 '{talker}' 发送URL")
                        else:
                            print(f"❌ 向群聊 '{talker}' 发送URL失败")
                            
                        # 每个群发送后等待一段时间
                        time.sleep(delay)
                        
                    print(f"--- 群日报URL发送完成: 成功 {success_count}/{len(valid_reports)} ---")
            except ImportError as e:
                print(f"❌ 导入wx_sender模块失败，请确保已安装pyautogui和pyperclip库: {str(e)}")
                logger.error(f"导入wx_sender模块失败: {str(e)}")
            except Exception as e:
                print(f"❌ 发送群日报URL到微信群失败: {str(e)}")
                logger.error(f"发送群日报URL到微信群失败: {str(e)}")
            
            # 自动同步URL到飞书多维表格
            try:
                from feishu_sender import send_urls_to_feishu_batch
                
                print("\n--- 开始同步群日报URL到飞书多维表格 ---")
                
                # 筛选需要同步到飞书的报告
                feishu_reports = [r for r in all_reports_info if r.get('auto_sync_to_feishu', False)]
                
                if not feishu_reports:
                    print("没有需要同步到飞书的群日报，跳过飞书同步步骤。")
                else:
                    # 批量发送URL到飞书
                    result = send_urls_to_feishu_batch(feishu_reports)
                    
                    if result['success'] > 0:
                        print(f"✅ 成功同步 {result['success']}/{result['total']} 个URL到飞书多维表格")
                    
                    if result['failed'] > 0:
                        print(f"⚠️ {result['failed']} 个URL同步失败，详情请查看日志")
                        
                    print("--- 飞书同步完成 ---")
            except ImportError as e:
                print(f"❌ 导入feishu_sender模块失败，请确保已安装requests库: {str(e)}")
                logger.error(f"导入feishu_sender模块失败: {str(e)}")
            except Exception as e:
                print(f"❌ 同步群日报URL到飞书失败: {str(e)}")
                logger.error(f"同步群日报URL到飞书失败: {str(e)}")

        print("-" * 50)
        print("🎉 所有任务处理完成！")
        print("-" * 50)

    except KeyboardInterrupt:
        print("\n❌ 用户中断处理")
        logger.info("用户中断处理")
    except Exception as e:
        print(f"\n❌ 处理出错: {str(e)}")
        logger.error(f"主程序处理过程中出错: {str(e)}")
        sys.exit(1)

    finally:
        # 确保关闭chatlog服务器，如果是我们启动的
        if server_process:
            print("⏳ 正在关闭数据服务...")
            server_process.terminate()
            print("✅ 数据服务已关闭")
            logger.info("Chatlog服务器已终止。")

        # 在程序结束时，如果有错误发生，打开错误日志文件
        if os.path.exists(log_filename) and os.path.getsize(log_filename) > 0:
            print(f"\n⚠️ 程序运行过程中发生了错误，错误日志已保存至: {log_filename}")
            log_path = os.path.join(os.path.dirname(__file__), log_filename)
            try:
                # 尝试在默认文本编辑器中打开日志文件
                if sys.platform == 'win32':
                    os.startfile(log_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(['open', log_path])
                else:  # Linux
                    subprocess.call(['xdg-open', log_path])
                print("✅ 已打开错误日志文件")
            except Exception as e:
                print(f"❌ 打开错误日志文件失败: {str(e)}")
                print(f"请手动打开错误日志文件查看: {log_path}")


if __name__ == "__main__":
    main()





