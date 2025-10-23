import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量（从GitHub Secrets读取）
load_dotenv()

# 飞书配置 - 这些值需要从环境变量或GitHub Secrets中读取
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")  # 多维表格的app_token
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID")    # 多维表格的table_id

# 微信读书Cookie
WEREAD_COOKIE = os.getenv("WEREAD_COOKIE")

# 飞书API端点
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_GET_TOKEN_URL = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
FEISHU_BITABLE_URL = f"{FEISHU_API_BASE}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"

def get_feishu_access_token():
    """获取飞书API的访问令牌（Access Token）"""
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    
    response = requests.post(FEISHU_GET_TOKEN_URL, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            return result.get("tenant_access_token")
        else:
            print(f"获取access_token失败: {result.get('msg')}")
    else:
        print(f"HTTP请求失败: {response.status_code}")
    return None

def get_weread_notebook():
    """从微信读书获取笔记本数据（复用你原有脚本的逻辑）"""
    # 这里简化表示，你可以将原有脚本中获取书单、划线、章节等函数逻辑迁移过来
    session = requests.Session()
    # 设置Cookie等逻辑...
    # 返回处理好的书籍列表
    books = []  # 假设这是获取到的书籍列表
    return books

def transform_book_to_feishu_record(book):
    """将微信读书的单本书数据转换为飞书多维表格所需的格式"""
    # 这是最关键的一步：字段映射。
    # 你需要根据你飞书表格里实际的列名（字段名）来设置key，根据微信读书返回的数据结构设置value。
    fields = {
        "书名": book.get("title"),
        "作者": book.get("author"),
        # "封面": [{"file_token": "封面图片的token"}], # 附件类型较复杂，初期可先忽略
        "阅读进度": book.get("readingProgress", 0),
        "阅读状态": "读完" if book.get("markedStatus") == 4 else "在读",
        # ... 其他字段映射
    }
    return {"fields": fields}

def batch_update_feishu_table(records, access_token):
    """批量将记录写入飞书多维表格"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    # 飞书API一次最多插入500条，但建议分小批次
    batch_size = 50
    for i in range(0, len(records), batch_size):
        batch_records = records[i:i + batch_size]
        data = {"records": [{"fields": r["fields"]} for r in batch_records]}
        
        response = requests.post(f"{FEISHU_BITABLE_URL}/batch_create", headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print(f"成功插入 {len(batch_records)} 条记录")
            else:
                print(f"插入记录失败: {result.get('msg')}")
        else:
            print(f"HTTP请求失败: {response.status_code}")

def main():
    """主函数"""
    print("开始同步微信读书数据到飞书...")
    
    # 1. 获取飞书访问令牌
    access_token = get_feishu_access_token()
    if not access_token:
        print("无法获取飞书访问令牌，同步终止。")
        return
    
    # 2. 获取微信读书数据
    print("正在从微信读书获取数据...")
    books = get_weread_notebook()
    if not books:
        print("未从微信读书获取到数据。")
        return
    print(f"从微信读书获取到 {len(books)} 本书的数据。")
    
    # 3. 数据格式转换
    print("正在转换数据格式...")
    feishu_records = []
    for book in books:
        record = transform_book_to_feishu_record(book)
        feishu_records.append(record)
    
    # 4. 写入飞书多维表格
    print("正在将数据写入飞书多维表格...")
    batch_update_feishu_table(feishu_records, access_token)
    
    print("同步流程结束！")

if __name__ == "__main__":
    main()
