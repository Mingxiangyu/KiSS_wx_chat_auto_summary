"""
微信群聊天记录提取、分析和可视化工具配置文件

此文件包含程序运行所需的所有默认配置参数
"""

# 应用默认设置



CHAT_DEMO_CFG = {
    **{
        "api_key": "AIzaSyDCCCBflusmQfvcEYcugVbjl5Sr6viDNJ4",  # 填写【Google Gemini】的 API Key。  （此处为我自用key，仅供测试，有效期较短，请自行申请）
        # "prompt_template_path": r"./prompt/【Simonlin佬】新版日报卡片版提示词(易用版).md",  # Prompt地址
        "prompt_template_path": r"./prompt/其它精选prompt/法贝尔鸟类插画风格/法贝尔鸟类插画风格.prompt.txt",  # Prompt地址
        # "prompt_template_path": r".\prompt\其它零散prompt\乔木群聊\群聊日报提示词V8.md",  # Prompt地址
        # "prompt_template_path": r"./prompt/【卡子哥与Simonlin佬】微信聊天记录可视化prompt.txt",  # Prompt地址
        # "prompt_template_path": r"./prompt/【R佬】赛博朋克-微信群聊数据可视化与深度分析prompt.md",  # Prompt地址
    },
    **{
        **{  # 微信4.x配置
            "wechat_data_dir": r"D:/Users/Administrator/Documents/xwechat_files/wxid_km81v7w6fe9422_0d04",
            "chatlog_work_dir": r"C:/Users/Administrator/Documents/chatlog/wxid_km81v7w6fe9422_0d04",
            "wx_version": "4",
        },
        **{  # 3.x 微信
            # "wechat_data_dir": r"D:/Users/Administrator/Documents/WeChat Files/wxid_xxxx",  # 【chatlog需要】
            # "chatlog_work_dir": r"C:/Users/Administrator/Documents/chatlog/wxid_xxxx",  # 【chatlog需要】
            # "wx_version": "3",
        },
    },
    "talkers": [  # 联系人、群聊配置，每个元素为一个字典，包含名称和个性化配置
        # {
        #     "name": "爱中华肯德基星期四(国资收购团伙)",
        #     # "prompt_template_path": r"./prompt/其它零散prompt/乔木群聊/群聊日报提示词V8.md",
        #     "prompt_template_path": r"./prompt/其它精选prompt/法贝尔鸟类插画风格/法贝尔鸟类插画风格.prompt.txt",
        #     "auto_generate_png": False,
        #     "auto_generate_url": True,
        #     "url_requires_password": True,
        #     "auto_send_to_wechat": True,
        #     "wechat_message_prefix": "群周报已生成：",
        #     "auto_sync_to_feishu": False,
        #     "related_link": {
        #         "text": "查看更多群日报",  # 链接显示的文本
        #         "url": "https://www.baidu.com/"  # 链接的目标URL
        #     }
        # },
        # "设计漫步",
        # "【懂车帝】奔驰GLC车主 交流群",
        # "奔驰GLC车主群",
        # "AIGC VIP群",
        # "Cursor Meetup Beijing 现场群6.28",
        # "狂热AI俱乐部",
        # "互联网高端产品群",
        # "Simonlin的兄弟姐妹",
        # "Bei 🅙♊️双子座生日快乐(5.21-6.21",
        # "AI自媒体创造营②🐬🦈🐋",
        "AI产品开发创造营⚽️🏀🏐",
        # "互联网行业交流（北京）",
    ],
    # 'days': 1,  # 获取最近多少天的聊天记录。当填写为0时，代表就只是当天。填写为1时，代表今天和昨天。命令行未指定时使用此值。
    'days': 7,  # 获取最近多少天的聊天记录。当填写为0时，代表就只是当天。填写为1时，代表今天和昨天。命令行未指定时使用此值。
    'auto_mode': True,  # 获取最近多少天的聊天记录。当填写为0时，代表就只是当天。填写为1时，代表今天和昨天。命令行未指定时使用此值。
    # 数据打码脱敏规则
    "data_masking_rules": {
        "小严同学": "NPC1号",
        "小严同学（goDog神走狗神）": "NPC2号"
    },
    # ——————————————————————————————————————
    # ——————————————————————————————————————
    # ——————————————————————————————————————
    **{
        "chatlog_server_ip_port": "127.0.0.1:5030",  # 服务器IP地址，与下方【chatlog_server_url】保持一致
        "chatlog_server_url": "http://127.0.0.1:5030",  # 服务器API地址
        "output_dir": r"./output",  # 输出的html地址
        "auto_open_browser": True,  # 是否自动打开浏览器
        "auto_generate_png": False,  # 是否自动生成PNG图片
        "auto_generate_url": True,  # 是否自动生成URL
        "url_requires_password": False,  # 是否自动生成URL
        "website_hosting_address":"http://139.196.112.100:8888",
        "chatlog_exe_path": "./chatlog/chatlog.exe",  # 开源项目chatlog的exe可执行程序。
        "manual_gui_auto_decryption": False,  # 是否需要手动启动GUI以获取最新数据
        "manual_gui_auto_decryption_wait_sec": 10,  # 等待N秒，秒数
    },
    **{  # 日志配置
        "log_dir": './logs',
        "logging_level": "INFO",
        "logging_format": '%(asctime)s - %(levelname)s - %(message)s',
        "logging_date_format": '%Y-%m-%d %H:%M:%S'
    },
    # Gemini API 调用相关配置
    'safety_margin_tokens': 5000,  # token计算时的安全边际，增加以避免超限
    'gemini_retry_attempts': 5,  # Gemini API调用失败时的最大重试次数
    'gemini_retry_delay_sec': 60,  # Gemini API调用失败时重试的等待秒数
    'gemini_max_input_tokens': 131072,  # Gemini模型的最大输入token限制
    'related_link': {
        'text': '查看更多群日报',  # 链接显示的文本
        'url': 'https://www.baidu.com/'  # 链接的目标URL
    },
    'auto_send_to_wechat':False,
    # 'auto_send_to_wechat':True,
    'wechat_send_delay_seconds':5,
    'wechat_message_prefix':"群周报已生成：",
    # 微信版本配置（用于wx_sender）
    'wechat_version_for_sender': 'auto',  # 可选值: 'auto', '3.9.0', '4.0.4', '4.0.5' 等
    # 'wechat_version_for_sender': '4.0.4',  # 如果自动检测不准确，可以手动指定版本
    # 飞书多维表格同步配置
    'auto_sync_to_feishu': False,
    'feishu_app_token': 'T87pbLkEman7EQsNRIoczyHsnHM',
    'feishu_table_id': 'tblEjyEQyBSLfpWq',
    # 飞书应用凭证，用于自动获取和刷新授权令牌
    'feishu_app_id': '',  # 请在此处填入飞书应用ID
    'feishu_app_secret': '',  # 请在此处填入飞书应用密钥
    # 以下授权令牌配置已不再需要手动填写，系统会自动获取和刷新
    # 'feishu_auth_token': 'u-cyJicVAdZeDoLdCTGrCl7iklgHi4hg0NjwG001KE0w9v' # 此令牌已过期
}
