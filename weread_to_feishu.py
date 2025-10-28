import os
import requests
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID")

# 微信读书配置
WEREAD_COOKIE = os.getenv("WEREAD_COOKIE")

# API端点
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_GET_TOKEN_URL = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
FEISHU_BITABLE_RECORDS_URL = f"{FEISHU_API_BASE}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"

WEREAD_NOTEBOOK_URL = "https://i.weread.qq.com/user/notebooks"

def get_feishu_access_token():
    """获取飞书访问令牌"""
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    try:
        response = requests.post(FEISHU_GET_TOKEN_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 0:
            logger.info("✅ 成功获取飞书访问令牌")
            return result.get("tenant_access_token")
        else:
            logger.error(f"❌ 获取飞书令牌失败: {result.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"❌ 请求飞书API失败: {str(e)}")
        return None

def get_weread_books():
    """获取微信读书笔记本数据"""
    headers = {
        "Cookie": WEREAD_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(WEREAD_NOTEBOOK_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        books = data.get("books", [])
        logger.info(f"📚 从微信读书获取到 {len(books)} 本书")
        return books
    except Exception as e:
        logger.error(f"❌ 获取微信读书数据失败: {str(e)}")
        return []

def transform_book_data(book):
    """将微信读书数据转换为飞书表格格式"""
    book_info = book.get("book", {})
    
    # 根据你的飞书表格字段名进行映射
    fields = {
        "书名": book_info.get("title", "未知书名"),
        "作者": book_info.get("author", "未知作者"),
        "阅读进度": book_info.get("readingProgress", 0) or 0,
        "阅读状态": "读完" if book_info.get("markedStatus") == 4 else "在读"
    }
    
    # 处理封面
    cover_url = book_info.get("cover", "")
    if cover_url and cover_url.startswith("http"):
        fields["封面"] = [{"type": "url", "text": cover_url}]
    
    # 处理完成日期
    finish_time = book_info.get("finishReadingTime")
    if finish_time:
        try:
            # 将时间戳转换为飞书支持的日期格式
            finish_date = datetime.fromtimestamp(finish_time).strftime("%Y-%m-%d")
            fields["完成阅读日期"] = finish_date
        except:
            pass
    
    logger.info(f"📖 处理书籍: {fields['书名']}")
    return fields

def add_record_to_feishu(record_data, access_token):
    """添加单条记录到飞书表格"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "fields": record_data
    }
    
    try:
        response = requests.post(FEISHU_BITABLE_RECORDS_URL, headers=headers, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            logger.info(f"✅ 成功添加记录: {record_data.get('书名', '未知')}")
            return True
        else:
            logger.error(f"❌ 添加记录失败: {result.get('msg')}")
            return False
    except Exception as e:
        logger.error(f"❌ 请求飞书表格API失败: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("🎬 开始同步流程...")
    
    # 检查环境变量
    required_vars = {
        "FEISHU_APP_ID": FEISHU_APP_ID,
        "FEISHU_APP_SECRET": FEISHU_APP_SECRET,
        "FEISHU_APP_TOKEN": FEISHU_APP_TOKEN,
        "FEISHU_TABLE_ID": FEISHU_TABLE_ID,
        "WEREAD_COOKIE": WEREAD_COOKIE
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        logger.error(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        return
    
    logger.info("✅ 所有环境变量检查通过")
    
    # 1. 获取飞书访问令牌
    access_token = get_feishu_access_token()
    if not access_token:
        return
    
    # 2. 获取微信读书数据
    books = get_weread_books()
    if not books:
        logger.info("📭 没有获取到书籍数据，同步结束")
        return
    
    # 3. 处理并同步每本书
    success_count = 0
    for book in books:
        try:
            # 转换数据格式
            record_data = transform_book_data(book)
            
            # 添加到飞书表格
            if add_record_to_feishu(record_data, access_token):
                success_count += 1
                
        except Exception as e:
            book_title = book.get("book", {}).get("title", "未知书籍")
            logger.error(f"❌ 处理书籍 {book_title} 时出错: {str(e)}")
            continue
    
    logger.info(f"🎉 同步完成! 成功处理 {success_count}/{len(books)} 本书")

if __name__ == "__main__":
    main()
