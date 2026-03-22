import os
import glob
import uvicorn
import re
import datetime
import difflib
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from urllib.parse import parse_qs

# ==========================================
# 🛑 1. 你的 Obsidian 仓库路径
<<<<<<< HEAD
OBSIDIAN_VAULT_PATH = r"C:\Users\CSL\Desktop\260221" 
=======
OBSIDIAN_VAULT_PATH = r"/www/The Ravens Nest/Obsidian_Vault/260221" 
>>>>>>> cfaaa47622cb546c35a945a70d71674d288b57a9

# 🛑 2. 黑名单禁区 (确保没有 ChatLogs！)
EXCLUDE_FOLDERS = ["未整理聊天记录"]

# 🛑 3. API 密钥配置
# 方式1：从环境变量读取（推荐）
API_KEY = os.environ.get("OBSIDIAN_MCP_API_KEY", "xR7#kWm9$vLp2!nQ")
# 方式2：直接在这里修改（不推荐，但可临时使用）
# API_KEY = "xR7#kWm9$vLp2!nQ"
# ==========================================

if not os.path.exists(OBSIDIAN_VAULT_PATH):
    print(f"⚠️ 警告: 找不到路径 {OBSIDIAN_VAULT_PATH}")

# --- 鉴权辅助函数 ---
def _check_auth(scope) -> bool:
    """检查请求头中的 Authorization: Bearer <token> 是否与预设密钥匹配"""
    headers = dict(scope.get("headers", []))
    # headers 中的键是 bytes，需要解码
    auth_header = headers.get(b"authorization", b"").decode()
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]  # 去掉 "Bearer " 前缀
    return token == API_KEY

async def _send_401(send):
    """发送 401 Unauthorized 响应"""
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": b"Unauthorized: Invalid or missing API key",
    })

# --- 安全工具：确保路径在仓库内 ---
def _is_safe_path(relative_path: str) -> bool:
    """检查相对路径是否安全（不包含 .. 且最终在仓库内）"""
    if os.path.isabs(relative_path):
        return False
    norm_path = os.path.normpath(relative_path)
    if norm_path.startswith('..') or os.path.isabs(norm_path):
        return False
    full_path = os.path.join(OBSIDIAN_VAULT_PATH, norm_path)
    return os.path.commonpath([full_path, OBSIDIAN_VAULT_PATH]) == OBSIDIAN_VAULT_PATH

# --- 新增：向指定文件追加内容 ---
def logic_append_to_note(file_path: str, content: str) -> str:
    """
    将内容追加到指定的已有笔记文件末尾。
    file_path: 相对于 Obsidian 仓库根目录的路径，如 "学习/技术进展.md"
    content: 要追加的内容（纯文本，Markdown 格式）
    """
    print(f"🟢 [追加请求] 目标文件: {file_path}")

    if not _is_safe_path(file_path):
        return f"❌ 非法路径：{file_path} 不在仓库内或包含危险字符。请使用相对路径，例如 '学习/技术进展.md'。"

    full_path = os.path.join(OBSIDIAN_VAULT_PATH, file_path)
    if not os.path.exists(full_path):
        return f"❌ 文件不存在：{file_path}。请确保文件已存在，然后再追加内容。"

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
        if content.strip().lower() in existing_content.lower():
            print("⚠️ 触发拦截：内容已完全存在于文件中，取消追加。")
            return f"⚠️ 追加取消：该内容已存在于 {file_path} 中，无需重复添加。"
    except Exception as e:
        print(f"查重失败，跳过查重: {e}")

    try:
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n{content}\n")
        return f"✅ 已成功将内容追加到 {file_path} 的末尾。"
    except Exception as e:
        return f"❌ 追加失败: {str(e)}"

# --- 原有 save_memory 逻辑（保持不变）---
def logic_save_memory(content: str, category: str = "") -> str:
    print(f"🟢[写入请求] AI尝试分类: {category}")
    
    valid_folders =[]
    try:
        for d in os.listdir(OBSIDIAN_VAULT_PATH):
            full_path = os.path.join(OBSIDIAN_VAULT_PATH, d)
            if os.path.isdir(full_path) and not d.startswith('.') and d not in EXCLUDE_FOLDERS:
                valid_folders.append(d)
    except Exception as e:
        return f"❌ 读取文件夹失败: {str(e)}"
        
    target_folder = ""
    
    if category in valid_folders:
        target_folder = category  
    elif category:
        matched =[f for f in valid_folders if category.lower() in f.lower() or f.lower() in category.lower()]
        if matched:
            target_folder = matched[0]
            print(f"💡 智能模糊匹配成功: [{category}] ->[{target_folder}]")

    if not target_folder:
        folder_list_str = "、".join(valid_folders)
        return f"❌ 写入失败：严禁擅自新建文件夹！分类【{category}】不存在。\n请务必从以下列表中选择最相关的重新保存：\n[{folder_list_str}]"
        
    file_path = os.path.join(OBSIDIAN_VAULT_PATH, target_folder, "AI自动归档记录.md")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            old_blocks = re.split(r'\n\s*[-*_]{3,}\s*\n', '\n' + existing_content + '\n')
            content_clean = content.strip().lower()
            for block in old_blocks:
                block_clean = block.replace("> **AI 自动归档**", "").strip().lower()
                if not block_clean: continue
                if content_clean in block_clean:
                    print("⚠️ 触发拦截：内容已被完全包含。")
                    return "⚠️ 保存已取消：该记忆的内容已被完全包含在历史记录中，无需重复记录。"
                similarity = difflib.SequenceMatcher(None, content_clean, block_clean).ratio()
                if similarity > 0.8:
                    print(f"⚠️ 触发拦截：内容相似度高达 {int(similarity*100)}%。")
                    return f"⚠️ 保存已取消：检测到记忆库中已有极度相似的记录（相似度 {int(similarity*100)}%）。\n如果需要补充新信息，请将新信息与原信息合并，或者确保补充内容有明显的区别后再重新保存。"
        except Exception as e:
            print(f"查重过程出错，跳过查重: {e}")

    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n> **AI 自动归档**\n{content}\n")
        return f"✅ 已成功将记忆追加到了已有文件夹【{target_folder}】下的 AI自动归档记录.md 中！"
    except Exception as e:
        return f"保存失败: {str(e)}"

def logic_append_daily_chat(content: str, target_date: str = None) -> str:
    if not target_date or str(target_date).strip() == "":
        target_date = datetime.date.today().strftime("%Y-%m-%d")
        
    print(f"📝[追加聊天] 目标日期: {target_date}")
    chatlog_dir = os.path.join(OBSIDIAN_VAULT_PATH, "ChatLogs")
    if not os.path.exists(chatlog_dir):
        os.makedirs(chatlog_dir)
        
    file_path = os.path.join(chatlog_dir, f"{target_date}.md")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read().lower()
            content_clean = content.strip().lower()
            if content_clean in existing_content:
                print("⚠️ 触发拦截：该聊天记录今日已存在。")
                return "⚠️ 追加取消：这段聊天记录已经保存在今天的日志中了，请勿重复记录！"
        except Exception as e:
            print(f"查重过程出错，跳过: {e}")

    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{content}\n")
        return f"✅ 已成功将聊天记录追加到 {target_date}.md 的末尾！"
    except Exception as e:
        return f"❌ 追加聊天记录失败: {str(e)}"
        
def logic_search_memory(query: str) -> str:
    print(f"🔵 [搜索请求] 原始关键词: {query}") 
    
    search_pattern = os.path.join(OBSIDIAN_VAULT_PATH, "**", "*.md")
    all_md_files = glob.glob(search_pattern, recursive=True)
    
    md_files =[]
    for f in all_md_files:
        if not any(bad in f for bad in EXCLUDE_FOLDERS):
            md_files.append(f)
            
    if not md_files: return "Obsidian 记忆库为空（或全在黑名单中）。"

    md_files.sort(key=lambda x: os.path.basename(x), reverse=True)

    keywords =[k.strip().lower() for k in query.split() if k.strip()]
    if not keywords: return "关键词无效。"

    all_matches =[]

    for file_path in md_files:
        try:
            rel_path = os.path.relpath(file_path, OBSIDIAN_VAULT_PATH)
            with open(file_path, "r", encoding="utf-8") as f:
                full_content = f.read()
                
            blocks = re.split(r'\n\s*[-*_]{3,}\s*\n', '\n' + full_content + '\n')
            
            for block in blocks:
                block = block.strip()
                if not block: continue
                
                searchable_text = f"{rel_path} {block}".lower()
                match_count = sum(1 for word in keywords if word in searchable_text)
                
                if match_count > 0:
                    all_matches.append({
                        "score": match_count,
                        "filename": rel_path,
                        "content": block
                    })
        except Exception as e:
            continue
            
    if not all_matches: 
        return f"未找到包含关键词 {keywords} 的内容。"

    all_matches.sort(key=lambda x: x["score"], reverse=True)

    final_result = ""
    added_count = 0
    MAX_LENGTH = 6000  
    
    for match in all_matches:
        block_text = f"【来自文件: {match['filename']}】\n{match['content']}\n\n====================\n\n"
        
        if len(final_result) + len(block_text) > MAX_LENGTH:
            if added_count == 0:
                final_result = block_text[:MAX_LENGTH] + "\n...(达到6000字上限，为了保护AI，已强行截断)...\n"
                added_count += 1
            break 
        else:
            final_result += block_text
            added_count += 1
            
    print(f"✅ 共搜出 {len(all_matches)} 块，打包 {added_count} 块发给 AI。")
    return final_result.strip()

# --- 3. 服务器定义 ---
server = Server("Obsidian-Smart-Deduplication")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return[
        types.Tool(
            name="save_memory",
            description="保存重要设定到 Obsidian 的指定分类中（自带查重功能，重复内容会被拒绝）",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记忆的具体内容"},
                    "category": {"type": "string", "description": "目标分类名称"}
                },
                "required":["content"]
            }
        ),
        types.Tool(
            name="search_memory",
            description="搜索 Obsidian。支持搜文件名、日期或内容关键词。",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required":["query"]
            }
        ),
        types.Tool(
            name="append_daily_chat",
            description="追加聊天记录到 ChatLogs 文件夹",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "target_date": {"type": "string"}
                },
                "required": ["content"]
            }
        ),
        types.Tool(
            name="append_to_note",
            description="向一个已有的 Obsidian 笔记文件末尾追加内容（不新建文件）。用于在特定文件中接着记录。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "相对于 Obsidian 仓库根目录的笔记路径，如 '学习/技术进展.md' 或 '项目A/会议记录.md'。"},
                    "content": {"type": "string", "description": "要追加的内容（Markdown 格式）"}
                },
                "required": ["file_path", "content"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "save_memory":
        category = arguments.get("category", "")
        res = logic_save_memory(arguments.get("content", ""), category)
        return[types.TextContent(type="text", text=res)]
    elif name == "search_memory":
        res = logic_search_memory(arguments.get("query", ""))
        return [types.TextContent(type="text", text=res)]
    elif name == "append_daily_chat":
        content = arguments.get("content", "")
        target_date = arguments.get("target_date") 
        res = logic_append_daily_chat(content, target_date)
        return[types.TextContent(type="text", text=res)]
    elif name == "append_to_note":
        file_path = arguments.get("file_path", "")
        content = arguments.get("content", "")
        if not file_path or not content:
            return [types.TextContent(type="text", text="❌ 错误：缺少 file_path 或 content 参数。")]
        res = logic_append_to_note(file_path, content)
        return [types.TextContent(type="text", text=res)]
    raise ValueError(f"未知工具: {name}")

# --- 4. 网络桥梁（添加鉴权）---
sse = SseServerTransport("/messages")

async def app(scope, receive, send):
    if scope.get("type") != "http": return
    path = scope.get("path")
    method = scope.get("method")
    
    # 对 /sse 和 /messages 路径进行鉴权
    if path in ("/sse", "/messages"):
        if not _check_auth(scope):
            await _send_401(send)
            return
    
    if path == "/sse" and method == "GET":
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
            
    elif path == "/messages" and method == "POST":
        await sse.handle_post_message(scope, receive, send)
        
    else:
        msg_start = dict(type="http.response.start", status=404, headers=list())
        msg_body = dict(type="http.response.body", body=b"Not Found")
        await send(msg_start)
        await send(msg_body)

if __name__ == "__main__":
    print(">>> 施工队打卡：防重复写入雷达 + 追加笔记工具 + API 鉴权 已启动！ <<<")
    print(f">>> 使用密钥: {API_KEY} (可从环境变量 OBSIDIAN_MCP_API_KEY 修改) <<<")
    uvicorn.run(app, host="0.0.0.0", port=8000)