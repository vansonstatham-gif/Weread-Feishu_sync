import os
import requests
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from retrying import retry

load_dotenv()

# 配置信息
WEREAD_COOKIE = os.getenv("WEREAD_COOKIE")
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID")

# API端点
WEREAD_NOTEBOOKS_URL = "https://i.weread.qq.com/user/notebooks"
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_BITABLE_URL = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"

def retry_if_result_none(result):
    """重试条件：结果为None或空列表"""
    return result is None or result == []

@retry(stop_max_attempt_number=3, wait_fixed=2000, retry_on_result=retry_if_result_none)
def get_weread_books_with_retry():
    """带重试机制的获取微信读书数据函数"""
    headers = {
        "Cookie": WEREAD_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://weread.qq.com/",
        "Origin": "https://weread.qq.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Connection": "keep-alive"
    }
    
    print("🔍 尝试获取微信读书数据...")
    
    try:
        response = requests.get(WEREAD_NOTEBOOKS_URL, headers=headers, timeout=10)
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            books = data.get("books", [])
            print(f"✅ 成功获取数据，响应键: {list(data.keys())}")
            print(f"📚 书籍数量: {len(books)}")
            
            if books:
                for i, book in enumerate(books[:3]):  # 只显示前3本作为示例
                    book_info = book.get("book", {})
                    print(f"   {i+1}. 《{book_info.get('title', '未知')}》 - {book_info.get('author', '未知')}")
            
            return books
        else:
            print(f"❌ 请求失败: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"🌐 网络请求异常: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        print(f"📋 JSON解析错误: {str(e)}")
        if hasattr(response, 'text'):
            print(f"响应内容: {response.text[:200]}")  # 显示前200字符
        return None

def get_feishu_access_token():
    """获取飞书访问令牌"""
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    try:
        response = requests.post(FEISHU_TOKEN_URL, headers=headers, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            print("✅ 成功获取飞书访问令牌")
            return result.get("tenant_access_token")
        else:
            print(f"❌ 获取飞书令牌失败: {result.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ 请求飞书API失败: {str(e)}")
        return None

def transform_book_to_feishu_record(book):
    """转换微信读书数据为飞书表格格式"""
    book_info = book.get("book", {})
    
    # 基础字段映射
    fields = {
        "书名": book_info.get("title", "未知书名"),
        "作者": book_info.get("author", "未知作者"),
        "阅读进度": book_info.get("readingProgress", 0) or 0,
        "阅读状态": "读完" if book_info.get("markedStatus") == 4 else "在读"
    }
    
    # 处理封面图片
    cover_url = book_info.get("cover", "")
    if cover_url and cover_url.startswith("http"):
        # 飞书表格的附件字段格式
        fields["封面"] = [{"text": cover_url, "type": "url"}]
    
    # 处理分类信息
    categories = book_info.get("categories")
    if categories:
        fields["分类"] = [x["title"] for x in categories]
    
    # 处理阅读时间
    if "finishReadingTime" in book_info:
        try:
            finish_time = datetime.fromtimestamp(book_info["finishReadingTime"])
            fields["完成时间"] = finish_time.strftime("%Y-%m-%d")
        except:
            pass
    
    print(f"📖 处理书籍: 《{fields['书名']}》")
    return {"fields": fields}

def batch_update_feishu_table(records, access_token):
    """批量更新飞书表格"""
    if not records:
        print("📭 没有可同步的记录")
        return False
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    success_count = 0
    batch_size = 10  # 飞书API建议小批量操作
    
    for i in range(0, len(records), batch_size):
        batch_records = records[i:i + batch_size]
        
        data = {
            "records": [
                {
                    "fields": record["fields"]
                } for record in batch_records
            ]
        }
        
        try:
            response = requests.post(
                f"{FEISHU_BITABLE_URL}/batch_create", 
                headers=headers, 
                json=data, 
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    success_count += len(batch_records)
                    print(f"✅ 成功插入 {len(batch_records)} 条记录")
                else:
                    print(f"❌ 插入记录失败: {result.get('msg')}")
            else:
                print(f"❌ HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 批量插入异常: {str(e)}")
        
        # 避免频繁请求，小批量间隔
        time.sleep(1)
    
    print(f"🎯 同步完成: {success_count}/{len(records)} 条记录成功")
    return success_count > 0

def validate_environment():
    """验证环境变量配置"""
    required_vars = {
        "WEREAD_COOKIE": WEREAD_COOKIE,
        "FEISHU_APP_ID": FEISHU_APP_ID,
        "FEISHU_APP_SECRET": FEISHU_APP_SECRET,
        "FEISHU_APP_TOKEN": FEISHU_APP_TOKEN,
        "FEISHU_TABLE_ID": FEISHU_TABLE_ID
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        return False
    
    print("✅ 所有环境变量检查通过")
    return True

def main():
    """主函数"""
    print("🚀 开始微信读书到飞书同步流程")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 验证环境配置
    if not validate_environment():
        return
    
    # 2. 获取飞书访问令牌
    access_token = get_feishu_access_token()
    if not access_token:
        return
    
    # 3. 获取微信读书数据（带重试机制）
    books = get_weread_books_with_retry()
    if not books:
        print("❌ 无法获取微信读书数据，同步终止")
        return
    
    # 4. 数据转换
    print("🔄 转换数据格式...")
    feishu_records = []
    for book in books:
        record = transform_book_to_feishu_record(book)
        feishu_records.append(record)
    
    # 5. 同步到飞书
    print("📤 同步数据到飞书...")
    success = batch_update_feishu_table(feishu_records, access_token)
    
    if success:
        print("🎉 同步流程完成！")
    else:
        print("💥 同步过程中出现错误")

if __name__ == "__main__":
    main()
