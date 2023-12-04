# 导入必要的库
import openai
import streamlit as st
from bs4 import BeautifulSoup
import requests
import pdfkit
import time

# 在这里设置你的OpenAI助手ID
assistant_id = 'asst_X2cj8mkpIqhvkWZbXj2Szrvf'

# 在这里设置你的OpenAI API密钥
openai.api_key = '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'

# 在侧边栏创建API密钥配置和其他功能
st.sidebar.header("验证")
password = st.sidebar.text_input("输入密码来验证使用资格", type="password")

# 验证密码
if password != '0000':
    st.error("请输入密码，否则无法使用此应用。")
    st.stop()

# 初始化OpenAI客户端（确保在应用内的侧边栏中设置你的API密钥）
client = openai

# 初始化文件ID和聊天控制的会话状态变量
if "file_id_list" not in st.session_state:
    st.session_state.file_id_list = []

if "start_chat" not in st.session_state:
    st.session_state.start_chat = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None


# 定义抓取、将文本转换为PDF和上传到OpenAI的函数
def scrape_website(url):
    """从网站URL抓取文本。"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()


def text_to_pdf(text, filename):
    """将文本内容转换为PDF文件。"""
    path_wkhtmltopdf = 'C:/GPTs/wkhtmltopdf/bin/wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    pdfkit.from_string(text, filename, configuration=config)
    return filename


def upload_to_openai(filepath):
    """将文件上传到OpenAI并返回其文件ID。"""
    with open(filepath, "rb") as file:
        response = openai.files.create(file=file.read(), purpose="assistants")
    return response.id


# 在侧边栏中为网页抓取和文件上传添加额外的功能
st.sidebar.header("功能")
website_url = st.sidebar.text_input("输入网站 URL 以抓取并组织成 PDF", key="website_url")

# 按钮用于抓取网站，转换为PDF，并上传到OpenAI
if st.sidebar.button("抓取并上传"):
    # 抓取，转换和上传过程
    scraped_text = scrape_website(website_url)
    pdf_path = text_to_pdf(scraped_text, "scraped_content.pdf")
    file_id = upload_to_openai(pdf_path)
    st.session_state.file_id_list.append(file_id)

# 侧边栏选项让用户上传自己的文件
uploaded_file = st.sidebar.file_uploader("上传文件到openai", key="file_uploader")

# 按钮用于上传用户的文件并存储文件ID
if st.sidebar.button("上传文件"):
    # 上传用户提供的文件
    if uploaded_file:
        with open(f"{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())
        additional_file_id = upload_to_openai(f"{uploaded_file.name}")
        st.session_state.file_id_list.append(additional_file_id)

# 显示所有文件ID
if st.session_state.file_id_list:
    st.sidebar.write("已上传的文件ID：")
    for file_id in st.session_state.file_id_list:
        st.sidebar.write(file_id)
        # 将文件关联到助手
        assistant_file = client.beta.assistants.files.create(
            assistant_id=assistant_id,
            file_id=file_id
        )

# 按钮用于开始聊天会话
if st.sidebar.button("开始对话"):
    # 在开始聊天之前检查是否已上传文件
    if st.session_state.file_id_list:
        st.session_state.start_chat = True
        # 创建一个线程并将其ID存储在会话状态中
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        st.write("线程id: ", thread.id)
    else:
        st.sidebar.warning("请上传至少一个文件以开始聊天。")


# 定义处理带有引文的消息的函数
def process_message_with_citations(message):
    """从消息中提取内容和注释，并将引文格式化为脚注。"""
    message_content = message.content[0].text
    annotations = message_content.annotations if hasattr(message_content, 'annotations') else []
    citations = []

    # 遍历注释并添加脚注
    for index, annotation in enumerate(annotations):
        # 用脚注替换文本
        message_content.value = message_content.value.replace(annotation.text, f' [{index + 1}]')

        # 根据注释属性收集引文
        if (file_citation := getattr(annotation, 'file_citation', None)):
            # 检索引用的文件详细信息 (这里是虚拟响应，因为我们不能调用OpenAI)
            cited_file = {'filename': 'cited_document.pdf'}  # 这应该被实际的文件检索替换
            citations.append(f'[{index + 1}] {file_citation.quote} from {cited_file["filename"]}')
        elif (file_path := getattr(annotation, 'file_path', None)):
            # 文件下载引用的占位符
            cited_file = {'filename': 'downloaded_document.pdf'}  # 这应该被实际的文件检索替换
            citations.append(
                f'[{index + 1}] Click [here](#) to download {cited_file["filename"]}')  # 下载链接应被实际的下载路径替换

    # 在消息内容的末尾添加脚注
    full_response = message_content.value + '\n\n' + '\n'.join(citations)
    return full_response


# 主聊天界面设置
st.title("OpenAI Assistants API 聊天")
st.write("这是一个简单的聊天应用，使用OpenAI的API生成回应。")

# 只有在开始聊天后才显示聊天界面
if st.session_state.start_chat:
    # 如果尚未在会话状态中，则初始化模型和消息列表
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4-1106-preview"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 显示聊天中的现有消息
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 用户的聊天输入
    if prompt := st.chat_input("你好吗？"):
        # 添加用户消息到状态并显示它
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 将用户的消息添加到现有的线程中
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt
        )

        # 创建一个run并附加额外的指令
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=assistant_id,
            instructions="请使用文件中提供的知识回答查询。当添加其他信息时，请以不同的颜色明确标记。"
        )

        # 轮询run是否完成并检索助手的消息
        while run.status != 'completed':
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread_id,
                run_id=run.id
            )

        # 检索助手添加的消息
        messages = client.beta.threads.messages.list(
            thread_id=st.session_state.thread_id
        )

        # 处理并显示助手消息
        assistant_messages_for_run = [
            message for message in messages
            if message.run_id == run.id and message.role == "assistant"
        ]
        for message in assistant_messages_for_run:
            full_response = process_message_with_citations(message)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            with st.chat_message("assistant"):
                st.markdown(full_response, unsafe_allow_html=True)
else:
    # 提示开始聊天
    st.write("请上传文件并点击 '开始聊天' 开始对话。")
