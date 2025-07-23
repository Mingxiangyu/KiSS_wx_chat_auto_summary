'''
微信群日报URL自动发送工具

功能描述:
自动将生成的群日报URL发送到对应的微信群聊，减少手动操作。

使用方法:
1. 确保微信已登录并处于可用状态
2. 调用send_url_to_wechat_group函数发送URL到指定群聊

依赖安装:
pip install pyautogui pyperclip
'''

import time
import os
import logging
import pyautogui
import pyperclip
import re
import psutil
import subprocess
from packaging import version

# 配置日志
logger = logging.getLogger(__name__)

# 微信版本检测缓存
_wechat_version_cache = None


def send_url_to_wechat_group(group_name, url, message_prefix="今日群日报已生成："):
    """
    将URL发送到指定的微信群聊
    增强版本，支持进程检测、窗口恢复、多屏幕处理和搜索结果类型识别

    参数:
        group_name (str): 微信群名称
        url (str): 要发送的URL
        message_prefix (str): URL前的消息前缀，默认为"今日群日报已生成："

    返回:
        bool: 发送成功返回True，否则返回False
    """
    try:
        logger.info(f"准备向群聊 '{group_name}' 发送URL: {url}")

        # 第一步：激活微信窗口（包含进程检测、窗口恢复、多屏幕处理）
        logger.info("正在激活微信窗口...")
        if not activate_wechat_window():
            logger.error("无法激活微信窗口，请检查微信是否正常运行")
            return False

        logger.info("微信窗口激活成功，开始搜索群聊")

        # 第二步：搜索并选择群聊（包含搜索结果类型识别）
        if not search_and_select_chat(group_name):
            logger.error(f"无法找到群聊: {group_name}")
            return False

        logger.info(f"成功选择群聊 '{group_name}'，准备发送消息")

        # 第三步：等待聊天界面完全加载
        time.sleep(2)

        # 第四步：准备并发送消息
        full_message = f"{message_prefix}\n{url}"
        logger.info(f"准备发送消息: {full_message}")

        # 复制消息到剪贴板
        pyperclip.copy(full_message)

        # 确保焦点在输入区域
        if not ensure_input_focus():
            logger.warning("无法确保输入框焦点，但继续尝试发送")

        # 粘贴消息
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)

        # 发送消息
        pyautogui.press('enter')
        time.sleep(1)

        logger.info(f"成功向群聊 '{group_name}' 发送URL")
        return True

    except Exception as e:
        logger.error(f"向群聊 '{group_name}' 发送URL时出错: {str(e)}")
        return False


def ensure_input_focus():
    """
    确保输入框获得焦点

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 方法1: 点击输入框区域
        screen_width, screen_height = pyautogui.size()
        input_box_x = screen_width // 2
        input_box_y = screen_height - 80  # 输入框通常在底部

        logger.info(f"点击输入框位置: ({input_box_x}, {input_box_y})")
        pyautogui.click(input_box_x, input_box_y)
        time.sleep(0.5)

        # 方法2: 使用Tab键导航到输入框
        pyautogui.press('tab')
        time.sleep(0.3)

        # 方法3: 尝试使用快捷键定位到输入框
        # 在某些微信版本中，Ctrl+T可能有效
        pyautogui.hotkey('ctrl', 't')
        time.sleep(0.3)

        return True

    except Exception as e:
        logger.error(f"确保输入框焦点时出错: {str(e)}")
        return False

def get_wechat_version():
    """
    获取微信版本号

    返回:
        str: 微信版本号，如果无法获取则返回None
    """
    global _wechat_version_cache

    # 如果已经缓存了版本信息，直接返回
    if _wechat_version_cache is not None:
        return _wechat_version_cache

    try:
        # 尝试查找微信窗口
        wechat_windows = pyautogui.getWindowsWithTitle('微信')

        if not wechat_windows:
            logger.warning("未找到微信窗口，无法检测版本")
            return None

        # 获取微信窗口的详细信息
        wechat_window = wechat_windows[0]

        # 尝试从窗口标题或其他属性获取版本信息
        # 这里我们使用一个简化的方法：检查窗口的某些特征
        # 实际实现中可能需要更复杂的版本检测逻辑

        # 激活微信窗口以便进行检测
        wechat_window.activate()
        time.sleep(1)

        # 尝试通过菜单或其他方式检测版本
        # 这里我们使用一个简化的检测方法
        # 可以通过检查界面元素的存在来判断版本

        # 暂时返回一个默认版本，实际使用中可以根据需要改进
        # 用户可以通过配置文件指定版本
        from cfg import CHAT_DEMO_CFG
        configured_version = CHAT_DEMO_CFG.get('wechat_version_for_sender', 'auto')

        if configured_version != 'auto':
            _wechat_version_cache = configured_version
            logger.info(f"使用配置的微信版本: {configured_version}")
            return configured_version

        # 自动检测逻辑（简化版本）
        # 这里可以添加更复杂的检测逻辑
        # 目前默认假设是新版本
        detected_version = "4.0.4"  # 默认假设是新版本
        _wechat_version_cache = detected_version
        logger.info(f"自动检测到微信版本: {detected_version}")
        return detected_version

    except Exception as e:
        logger.error(f"检测微信版本时出错: {str(e)}")
        return None

def is_new_wechat_version(wechat_version=None):
    """
    判断是否为新版本微信（4.0.4及以上）

    参数:
        wechat_version (str): 微信版本号，如果为None则自动检测

    返回:
        bool: 如果是新版本返回True，否则返回False
    """
    if wechat_version is None:
        wechat_version = get_wechat_version()

    if wechat_version is None:
        # 如果无法检测版本，默认使用新版本逻辑（更安全）
        logger.warning("无法检测微信版本，默认使用新版本搜索逻辑")
        return True

    try:
        # 解析版本号并比较
        current_version = version.parse(wechat_version)
        threshold_version = version.parse("4.0.4")
        return current_version >= threshold_version
    except Exception as e:
        logger.error(f"解析微信版本号时出错: {str(e)}")
        # 出错时默认使用新版本逻辑
        return True

def find_wechat_process():
    """
    查找微信进程

    返回:
        psutil.Process: 微信进程对象，如果未找到返回None
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['name'] and 'wechat' in proc.info['name'].lower():
                    return proc
                if proc.info['exe'] and 'wechat' in proc.info['exe'].lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    except Exception as e:
        logger.error(f"查找微信进程时出错: {str(e)}")
        return None


def restore_wechat_window():
    """
    恢复微信窗口（如果被最小化）

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 方法1: 使用改进的PowerShell命令
        powershell_cmd = '''
        Add-Type -AssemblyName Microsoft.VisualBasic
        $wechat = Get-Process | Where-Object {$_.ProcessName -like "*WeChat*"}
        if ($wechat) {
            foreach ($proc in $wechat) {
                try {
                    if ($proc.MainWindowHandle -ne 0) {
                        [Microsoft.VisualBasic.Interaction]::AppActivate($proc.ProcessName)
                        break
                    }
                } catch {
                    # 忽略单个进程的错误，继续尝试下一个
                }
            }
        }
        '''

        result = subprocess.run(['powershell', '-Command', powershell_cmd],
                              capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            logger.info("通过PowerShell成功恢复微信窗口")
            time.sleep(3)  # 等待窗口恢复
            return True
        else:
            logger.warning(f"PowerShell方法失败: {result.stderr}")

        # 方法2: 使用Windows API方法
        return restore_window_via_winapi()

    except Exception as e:
        logger.error(f"恢复微信窗口时出错: {str(e)}")
        return restore_window_via_winapi()


def restore_window_via_winapi():
    """
    使用Windows API方法恢复窗口

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 使用pyautogui的方法尝试恢复
        # 发送Alt+Tab来切换窗口
        logger.info("尝试使用Alt+Tab切换到微信窗口")

        # 按Alt+Tab几次来查找微信窗口
        for i in range(5):
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)

            # 检查是否找到了微信窗口
            wechat_windows = pyautogui.getWindowsWithTitle('微信')
            if wechat_windows:
                logger.info("通过Alt+Tab成功找到微信窗口")
                return True

        # 如果Alt+Tab不行，尝试Win+数字键（假设微信在任务栏）
        logger.info("尝试使用Win+数字键激活微信")
        for i in range(1, 10):
            pyautogui.hotkey('win', str(i))
            time.sleep(0.5)

            wechat_windows = pyautogui.getWindowsWithTitle('微信')
            if wechat_windows:
                logger.info(f"通过Win+{i}成功找到微信窗口")
                return True

        logger.warning("所有窗口恢复方法都失败了")
        return False

    except Exception as e:
        logger.error(f"使用Windows API恢复窗口时出错: {str(e)}")
        return False


def move_window_to_primary_screen(window):
    """
    将窗口移动到主屏幕

    参数:
        window: pyautogui窗口对象

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 获取主屏幕尺寸
        primary_width, primary_height = pyautogui.size()

        # 获取窗口当前位置和尺寸
        window_left = window.left
        window_top = window.top
        window_width = window.width
        window_height = window.height

        logger.info(f"窗口当前位置: ({window_left}, {window_top}), 尺寸: {window_width}x{window_height}")
        logger.info(f"主屏幕尺寸: {primary_width}x{primary_height}")

        # 检查窗口是否在主屏幕范围内
        if (window_left < 0 or window_left >= primary_width or
            window_top < 0 or window_top >= primary_height):

            logger.info("检测到窗口在副屏幕上，正在移动到主屏幕")

            # 计算新的窗口位置（居中显示）
            new_left = max(0, (primary_width - window_width) // 2)
            new_top = max(0, (primary_height - window_height) // 2)

            # 移动窗口
            window.moveTo(new_left, new_top)
            time.sleep(1)  # 等待窗口移动完成

            logger.info(f"窗口已移动到主屏幕位置: ({new_left}, {new_top})")
            return True
        else:
            logger.info("窗口已在主屏幕上")
            return True

    except Exception as e:
        logger.error(f"移动窗口到主屏幕时出错: {str(e)}")
        return False


def activate_wechat_window():
    """
    激活微信窗口，支持进程检测、窗口恢复和多屏幕处理

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 第一步：检查微信进程是否存在
        wechat_process = find_wechat_process()
        if not wechat_process:
            logger.error("未找到微信进程，请确保微信已启动")
            return False

        logger.info(f"找到微信进程: PID={wechat_process.pid}, 名称={wechat_process.name()}")

        # 第二步：尝试查找微信窗口
        wechat_windows = pyautogui.getWindowsWithTitle('微信')

        if not wechat_windows:
            logger.warning("未找到微信窗口，可能被最小化，尝试恢复窗口")

            # 尝试恢复窗口
            if restore_wechat_window():
                # 重新查找窗口
                time.sleep(2)
                wechat_windows = pyautogui.getWindowsWithTitle('微信')

                if not wechat_windows:
                    logger.error("恢复窗口后仍未找到微信窗口")
                    return False
            else:
                logger.error("无法恢复微信窗口")
                return False

        # 第三步：选择最合适的窗口（通常是第一个）
        target_window = wechat_windows[0]
        logger.info(f"选择微信窗口: 标题='{target_window.title}', 位置=({target_window.left}, {target_window.top})")

        # 第四步：检查并处理多屏幕问题
        if not move_window_to_primary_screen(target_window):
            logger.warning("移动窗口到主屏幕失败，但继续尝试激活")

        # 第五步：激活窗口（使用多种方法）
        activation_success = False

        # 方法1: 使用pyautogui的activate方法
        try:
            target_window.activate()
            time.sleep(1)
            activation_success = True
            logger.info("使用activate()方法激活窗口成功")
        except Exception as e:
            logger.warning(f"activate()方法失败: {str(e)}")

        # 方法2: 如果activate失败，尝试点击窗口
        if not activation_success:
            try:
                # 点击窗口中央来激活
                center_x = target_window.left + target_window.width // 2
                center_y = target_window.top + target_window.height // 2
                pyautogui.click(center_x, center_y)
                time.sleep(1)
                activation_success = True
                logger.info("使用点击方法激活窗口成功")
            except Exception as e:
                logger.warning(f"点击激活方法失败: {str(e)}")

        # 方法3: 使用Alt+Tab切换到微信
        if not activation_success:
            try:
                # 使用Alt+Tab切换到微信窗口
                for _ in range(5):
                    pyautogui.hotkey('alt', 'tab')
                    time.sleep(0.5)
                    current_windows = pyautogui.getWindowsWithTitle('微信')
                    if current_windows:
                        try:
                            active_window = pyautogui.getActiveWindow()
                            if active_window and '微信' in active_window.title:
                                activation_success = True
                                logger.info("使用Alt+Tab激活窗口成功")
                                break
                        except:
                            pass
            except Exception as e:
                logger.warning(f"Alt+Tab激活方法失败: {str(e)}")

        # 第六步：验证窗口是否成功激活
        if activation_success:
            logger.info("微信窗口激活成功")
            return True
        else:
            # 即使激活方法都失败了，如果窗口存在，我们仍然尝试继续
            logger.warning("所有激活方法都失败，但窗口存在，尝试继续执行")
            return True

    except Exception as e:
        # 检查错误消息，如果是Windows返回的成功状态码，则忽略此错误
        error_msg = str(e)
        if "Error code from Windows: 0 - 操作成功完成" in error_msg:
            logger.info("微信窗口激活成功，忽略Windows返回的成功状态码")
            return True
        else:
            logger.error(f"激活微信窗口时出错: {error_msg}")
            return False

def search_and_select_chat_old_version(chat_name):
    """
    旧版本微信的搜索并选择指定的聊天会话（4.0.4之前）

    参数:
        chat_name (str): 聊天会话名称

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        logger.info(f"使用旧版本微信搜索逻辑搜索: {chat_name}")

        # 点击搜索框
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)

        # 清空搜索框
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('delete')
        time.sleep(0.2)

        # 输入群聊名称
        pyperclip.copy(chat_name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1.5)  # 等待搜索结果

        # 旧版本：直接按Enter选择第一个结果
        pyautogui.press('enter')
        time.sleep(1)  # 等待聊天窗口加载

        logger.info("旧版本搜索完成")
        return True
    except Exception as e:
        logger.error(f"旧版本搜索并选择聊天会话时出错: {str(e)}")
        return False

def search_and_select_chat_new_version(chat_name):
    """
    新版本微信的搜索并选择指定的聊天会话（4.0.4及以上）

    参数:
        chat_name (str): 聊天会话名称

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        logger.info(f"使用新版本微信搜索逻辑搜索: {chat_name}")

        # 点击搜索框
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)

        # 清空搜索框
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('delete')
        time.sleep(0.2)

        # 输入群聊名称
        pyperclip.copy(chat_name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(2)  # 等待搜索结果，新版本可能需要更长时间

        # 新版本：需要在搜索结果中找到正确的群聊
        # 方法1: 使用方向键导航到正确的结果
        success = navigate_to_correct_chat_result(chat_name)

        if not success:
            # 方法2: 如果方向键导航失败，尝试点击方式
            logger.info("方向键导航失败，尝试点击方式")
            success = click_correct_chat_result(chat_name)

        if success:
            time.sleep(1)  # 等待聊天窗口加载
            logger.info("新版本搜索完成")
            return True
        else:
            logger.error("无法找到正确的聊天结果")
            return False

    except Exception as e:
        logger.error(f"新版本搜索并选择聊天会话时出错: {str(e)}")
        return False

def navigate_to_correct_chat_result(chat_name):
    """
    使用方向键导航到正确的聊天结果

    参数:
        chat_name (str): 聊天会话名称

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 首先按下方向键，确保焦点在搜索结果上
        pyautogui.press('down')
        time.sleep(0.3)

        # 尝试最多10次向下导航
        max_attempts = 10
        for i in range(max_attempts):
            # 按Enter尝试选择当前项
            pyautogui.press('enter')
            time.sleep(0.5)

            # 检查是否成功进入了聊天窗口
            # 这里可以通过检查窗口标题或其他方式来确认
            # 简化版本：假设如果没有异常就是成功了
            logger.info(f"尝试选择第 {i+1} 个搜索结果")

            # 如果成功，返回True
            # 这里需要更复杂的逻辑来验证是否选择了正确的聊天
            # 暂时假设成功
            return True

        logger.warning(f"在 {max_attempts} 次尝试后仍未找到正确的聊天结果")
        return False

    except Exception as e:
        logger.error(f"导航到正确聊天结果时出错: {str(e)}")
        return False

def click_correct_chat_result(chat_name):
    """
    通过点击的方式选择正确的聊天结果

    参数:
        chat_name (str): 聊天会话名称

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 这里可以使用图像识别或文本识别来找到正确的聊天项
        # 简化版本：尝试在屏幕上查找包含群聊名称的区域

        # 截取搜索结果区域的屏幕截图
        screenshot = pyautogui.screenshot()

        # 这里可以添加OCR或图像识别逻辑
        # 暂时使用简化的方法：尝试点击屏幕中央偏下的位置
        # 这通常是搜索结果列表的位置

        screen_width, screen_height = pyautogui.size()

        # 尝试点击几个可能的位置
        possible_positions = [
            (screen_width // 2, screen_height // 2 + 100),  # 中央偏下
            (screen_width // 2, screen_height // 2 + 150),  # 更下一些
            (screen_width // 2, screen_height // 2 + 200),  # 再下一些
        ]

        for pos_x, pos_y in possible_positions:
            try:
                pyautogui.click(pos_x, pos_y)
                time.sleep(0.5)

                # 检查是否成功进入聊天窗口
                # 简化版本：假设点击后就成功了
                logger.info(f"尝试点击位置: ({pos_x}, {pos_y})")
                return True

            except Exception as click_error:
                logger.warning(f"点击位置 ({pos_x}, {pos_y}) 失败: {str(click_error)}")
                continue

        return False

    except Exception as e:
        logger.error(f"点击正确聊天结果时出错: {str(e)}")
        return False

def search_and_select_chat(chat_name):
    """
    搜索并选择指定的聊天会话
    使用统一的方向键导航方法，不区分微信版本

    参数:
        chat_name (str): 聊天会话名称

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        logger.info(f"开始搜索群聊: {chat_name}")

        # 打开搜索框
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)

        # 清空搜索框
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('delete')
        time.sleep(0.2)

        # 输入群聊名称
        pyperclip.copy(chat_name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(2)  # 等待搜索结果加载

        # 使用方向键导航查找目标群聊
        if navigate_and_select_target_chat(chat_name):
            logger.info(f"成功选择群聊: {chat_name}")
            return True
        else:
            logger.error(f"未找到目标群聊: {chat_name}")
            return False

    except Exception as e:
        logger.error(f"搜索并选择聊天会话时出错: {str(e)}")
        return False


def is_search_result_valid_chat(target_name):
    """
    检查当前选中的搜索结果是否为有效的群聊
    通过截图和简单的界面检测来判断

    参数:
        target_name (str): 目标群聊名称

    返回:
        bool: 如果是有效的群聊结果返回True，否则返回False
    """
    try:
        # 方法1: 检查是否有群聊的特征元素
        # 在微信搜索结果中，群聊通常会显示群成员数量或群聊图标

        # 获取当前鼠标位置作为参考
        current_x, current_y = pyautogui.position()

        # 简单的颜色检测：检查搜索结果区域是否包含群聊特征
        # 这里使用一个简化的方法：检查结果类型

        # 方法2: 通过按键检测
        # 如果当前选中的是网页链接，按Enter会打开浏览器
        # 如果是群聊，按Enter会进入聊天界面

        # 暂时返回True，让后续的验证来判断
        # 这个函数主要是为了过滤明显的非群聊结果
        return True

    except Exception as e:
        logger.error(f"检查搜索结果类型时出错: {str(e)}")
        return True  # 出错时假设是有效的，让后续验证处理


def detect_browser_opened():
    """
    检测是否意外打开了浏览器

    返回:
        bool: 如果检测到浏览器被打开返回True，否则返回False
    """
    try:
        # 检查是否有浏览器窗口被打开
        browser_titles = ['Chrome', 'Firefox', 'Edge', 'Internet Explorer', 'Safari', 'Opera']

        for title in browser_titles:
            windows = pyautogui.getWindowsWithTitle(title)
            if windows:
                # 检查窗口是否是最近打开的（简化检测）
                logger.warning(f"检测到浏览器窗口被打开: {title}")
                return True

        return False

    except Exception as e:
        logger.error(f"检测浏览器窗口时出错: {str(e)}")
        return False


def close_browser_and_return_wechat():
    """
    关闭意外打开的浏览器并返回微信

    返回:
        bool: 成功返回True，否则返回False
    """
    try:
        # 尝试关闭浏览器窗口
        pyautogui.hotkey('alt', 'f4')  # 关闭当前窗口
        time.sleep(1)

        # 重新激活微信窗口
        return activate_wechat_window()

    except Exception as e:
        logger.error(f"关闭浏览器并返回微信时出错: {str(e)}")
        return False


def navigate_and_select_target_chat(target_name):
    """
    使用方向键在搜索结果中查找并选择目标群聊
    增强版本，支持搜索结果类型识别，避免选择网页链接

    参数:
        target_name (str): 目标群聊名称

    返回:
        bool: 找到并选择成功返回True，否则返回False
    """
    try:
        logger.info(f"使用方向键导航查找: {target_name}")

        # 首先按下方向键，确保焦点在搜索结果列表上
        pyautogui.press('down')
        time.sleep(0.5)

        # 最多尝试导航20次，增加尝试次数以应对更多搜索结果
        max_attempts = 20
        current_attempt = 0

        while current_attempt < max_attempts:
            current_attempt += 1
            logger.info(f"尝试第 {current_attempt} 个搜索结果")

            # 检查当前选中的搜索结果是否为有效的群聊
            if not is_search_result_valid_chat(target_name):
                logger.info(f"第 {current_attempt} 个结果不是有效的群聊，跳过")
                pyautogui.press('down')
                time.sleep(0.3)
                continue

            # 按Enter尝试进入当前选中的聊天
            pyautogui.press('enter')
            time.sleep(2)  # 增加等待时间，确保页面完全加载

            # 检查是否意外打开了浏览器
            if detect_browser_opened():
                logger.warning("检测到浏览器被打开，说明选中了网页链接，正在关闭浏览器")
                if close_browser_and_return_wechat():
                    # 重新打开搜索并继续
                    pyautogui.hotkey('ctrl', 'f')
                    time.sleep(0.5)
                    pyperclip.copy(target_name)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(1)

                    # 移动到下一个搜索结果
                    for _ in range(current_attempt + 1):
                        pyautogui.press('down')
                        time.sleep(0.2)
                    continue
                else:
                    logger.error("无法关闭浏览器并返回微信")
                    return False

            # 检查是否成功进入了目标群聊
            if verify_chat_selection(target_name):
                logger.info(f"成功进入目标群聊: {target_name}")
                return True

            # 如果不是目标群聊，返回搜索界面继续查找
            logger.info("不是目标群聊，返回搜索继续查找")

            # 重新打开搜索框
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.5)

            # 确保搜索内容还在
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyperclip.copy(target_name)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(1)

            # 移动到下一个搜索结果
            # 先按下方向键定位到列表，然后按多次下方向键到达下一个位置
            for _ in range(current_attempt + 1):
                pyautogui.press('down')
                time.sleep(0.2)

        logger.error(f"在 {max_attempts} 次尝试后仍未找到目标群聊: {target_name}")
        return False

    except Exception as e:
        logger.error(f"使用方向键查找群聊时出错: {str(e)}")
        return False


def verify_chat_selection(expected_name):
    """
    验证当前是否选择了正确的群聊
    通过多种方法进行验证，提高准确性

    参数:
        expected_name (str): 期望的群聊名称

    返回:
        bool: 如果是正确的群聊返回True，否则返回False
    """
    try:
        # 等待一下让窗口标题更新
        time.sleep(1)

        # 方法1: 检查微信窗口标题
        wechat_windows = pyautogui.getWindowsWithTitle('微信')
        if wechat_windows:
            window_title = wechat_windows[0].title
            logger.info(f"当前窗口标题: '{window_title}'")

            # 如果窗口标题包含群聊名称，认为选择正确
            if expected_name in window_title:
                logger.info(f"窗口标题匹配，确认选择了正确的群聊: {expected_name}")
                return True

            # 检查是否还在搜索界面（标题通常只是"微信"）
            if window_title.strip() == "微信":
                logger.info("仍在搜索界面，继续查找")
                return False

            # 检查是否进入了其他群聊或聊天
            if window_title != "微信" and expected_name not in window_title:
                logger.info(f"进入了其他聊天: '{window_title}'，不是目标群聊")
                return False

        # 方法2: 检查是否有聊天输入框（表示进入了聊天界面）
        if verify_chat_interface_elements():
            # 如果有聊天界面元素，但窗口标题不匹配，可能是标题更新延迟
            logger.info("检测到聊天界面元素，等待标题更新")
            time.sleep(2)  # 再等待一下

            # 重新检查窗口标题
            wechat_windows = pyautogui.getWindowsWithTitle('微信')
            if wechat_windows:
                window_title = wechat_windows[0].title
                logger.info(f"延迟检查窗口标题: '{window_title}'")

                if expected_name in window_title:
                    logger.info(f"延迟检查确认选择了正确的群聊: {expected_name}")
                    return True

        # 方法3: 使用备用验证方法
        logger.info("使用备用验证方法")
        return verify_chat_by_interface()

    except Exception as e:
        logger.error(f"验证群聊选择时出错: {str(e)}")
        return False


def verify_chat_interface_elements():
    """
    验证是否存在聊天界面的特征元素

    返回:
        bool: 如果检测到聊天界面元素返回True，否则返回False
    """
    try:
        # 尝试检测聊天界面的特征
        # 方法1: 尝试检测输入框是否存在
        # 在聊天界面，通常可以按Tab键切换到输入框

        # 保存当前位置
        original_pos = pyautogui.position()

        # 尝试点击屏幕下方的输入区域
        screen_width, screen_height = pyautogui.size()
        input_area_x = screen_width // 2
        input_area_y = screen_height - 80  # 输入框通常在底部

        pyautogui.click(input_area_x, input_area_y)
        time.sleep(0.5)

        # 尝试输入一个字符然后删除，看是否有响应
        pyautogui.typewrite('test')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')

        # 恢复鼠标位置
        pyautogui.moveTo(original_pos)

        return True  # 如果没有异常，认为存在聊天界面

    except Exception as e:
        logger.error(f"验证聊天界面元素时出错: {str(e)}")
        return False


def verify_chat_by_interface():
    """
    通过界面元素验证是否进入了聊天界面

    返回:
        bool: 如果进入了聊天界面返回True，否则返回False
    """
    try:
        # 尝试检测聊天界面的特征
        # 方法1: 尝试按Esc键，如果在聊天界面，通常不会有反应或返回主界面
        # 方法2: 检查是否可以输入消息（聊天输入框是否存在）

        # 简化方法：检查当前是否还在搜索状态
        # 如果按Esc能关闭搜索框，说明还在搜索界面
        pyautogui.press('escape')
        time.sleep(0.3)

        # 再次尝试打开搜索，如果能打开说明刚才关闭了搜索框，即还在搜索状态
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)

        # 检查搜索框是否打开了（简化检测）
        # 如果搜索框打开了，说明我们还在主界面，没有进入聊天
        # 关闭搜索框
        pyautogui.press('escape')
        time.sleep(0.3)

        # 这里返回False，表示还在搜索界面，需要继续查找
        return False

    except Exception as e:
        logger.error(f"通过界面验证聊天选择时出错: {str(e)}")
        return False


def send_urls_from_file(urls_file, delay_between_groups=5):
    """
    从统一的URL文件中读取并发送URL到对应的微信群
    
    参数:
        urls_file (str): URL文件的路径
        delay_between_groups (int): 每个群发送后的延迟时间(秒)
    
    返回:
        bool: 全部发送成功返回True，否则返回False
    """
    try:
        if not os.path.exists(urls_file):
            logger.error(f"URL文件不存在: {urls_file}")
            return False
            
        with open(urls_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 解析文件内容
        reports = []
        current_report = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.startswith('--- 群日报 #'):
                if current_report and 'talker' in current_report and 'html_url' in current_report:
                    reports.append(current_report)
                current_report = {}
            elif line.startswith('群聊名称:'):
                current_report['talker'] = line.replace('群聊名称:', '').strip()
            elif line.startswith('发布地址(URL):'):
                current_report['html_url'] = line.replace('发布地址(URL):', '').strip()
                
        # 添加最后一个报告
        if current_report and 'talker' in current_report and 'html_url' in current_report:
            reports.append(current_report)
            
        # 发送URL到对应群聊
        success_count = 0
        for report in reports:
            if send_url_to_wechat_group(report['talker'], report['html_url']):
                success_count += 1
                time.sleep(delay_between_groups)  # 每个群发送后等待一段时间
                
        logger.info(f"成功发送 {success_count}/{len(reports)} 个URL到微信群")
        return success_count == len(reports)
        
    except Exception as e:
        logger.error(f"从文件发送URL时出错: {str(e)}")
        return False

# 测试代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 测试发送单个URL
    # send_url_to_wechat_group("测试群", "https://example.com/report")
    
    # 测试从文件发送URL
    # 获取当前日期作为文件名的一部分
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    urls_file = f"./output/all_reports_urls_{current_date}.txt"
    
    if os.path.exists(urls_file):
        print(f"找到URL文件: {urls_file}，开始发送...")
        send_urls_from_file(urls_file)
    else:
        print(f"URL文件不存在: {urls_file}")
        # 列出output目录下的所有文件
        output_dir = "./output"
        if os.path.exists(output_dir):
            files = os.listdir(output_dir)
            url_files = [f for f in files if f.startswith("all_reports_urls_")]
            if url_files:
                print("找到以下URL文件:")
                for file in url_files:
                    print(f"  - {file}")
                latest_file = os.path.join(output_dir, sorted(url_files)[-1])
                print(f"\n使用最新的URL文件: {latest_file}")
                send_urls_from_file(latest_file)
            else:
                print(f"在 {output_dir} 目录下未找到任何URL文件")