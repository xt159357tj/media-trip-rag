import os
import ffmpeg

from fastmcp import FastMCP
from datetime import datetime
from langchain_tavily import TavilySearch

from core.logger import get_logger
from core.whisper import get_whisper, format_srt_timestamp
from config.settings import settings

logger = get_logger(__name__)

# 0. 初始化
mcp = FastMCP(settings.MCP_SERVER_NAME)

tavily_client = TavilySearch(
    tavily_api_key=settings.TAVILY_API_KEY,
    max_results=settings.TAVILY_MAX_RESULTS,
    include_answer=True,
)


# 1. prompt(s)
# 1-1. review prompt
@mcp.prompt()
def review_subtitle_prompt(content: str) -> str:
    """
    创建一个用于审核 SRT 字幕文件的 Prompt。
    """
    return f"""
你是一位精通音视频理解的专业字幕校对专家。
我会为你提供一段【音频流】以及对应的【Whisper 自动转录字幕文本】。

**任务目标：**
请结合音频中的实际语境、重音、停顿以及说话者的语气，对字幕内容进行“音文一致性”校对，并给出修改建议。

**全模态校验重点：**
1. **音文匹配（核心）：** 听音频，检查字幕是否出现了同音误判（例如将“集成”听成“继承”）。
2. **口语过滤：** 识别音频中的冗余语气词（如“呃”、“那个”、“然后”等停顿词），在不影响语义前提下建议删除，使字幕更精炼。
3. **断句优化：** 结合音频中的停顿（Pause）和呼吸感，检查当前的 SRT 时间轴断句是否符合自然语言逻辑。
4. **专有名词校正：** 结合上下文语义，修正音频中提到的技术术语、品牌名或人名。
5. **情感标注（可选）：** 如果音频中有明显的语气转折（如讽刺、激动、低语），请在建议中注明是否需要添加括号注释。

**输入字幕内容：**
{content}

**输出格式要求：**
请列出所有的修改建议，格式如下：
- [序号] 时间戳：{{"原文内容"}} -> 修改建议：{{"修正后的内容"}} (原因：结合音频听感说明，如“音频中发音清晰为XX”、“此处有明显停顿，建议断句”)
- 总体评价：如果字幕与音频完全匹配且表达流畅，请回复“校验通过”。
"""

# 1-2. rewrite prompt
@mcp.prompt()
def rewrite_subtitle_prompt(content: str, review_feedback: str) -> str:
    return f"""
你是一位精通字幕格式化处理的编辑。

**任务说明：**
参考下方的【修改建议】，对原始字幕文件内容`{content}`进行最终修正。

**规则：**
1. **保持格式：** 必须严格遵守 SRT 格式（序号、时间轴、文本内容）。
2. **严禁改动时间轴：** 除非修改建议中明确指出时间轴有重叠或严重错误，否则请勿改动，例如 `00:00:00,000 --> 00:00:00,000` 这一行。
3. **仅输出结果：** 请直接输出完整的、修正后的 SRT 文件内容，不要包含任何解释、开场白或结束语，以便我直接保存。

**修改建议：**
{review_feedback}

**现在，请输出修正后的完整 SRT 内容：**
"""

# 1-3. second_review_prompt
@mcp.prompt()
def second_review_prompt(content: str, review_feedback: str) -> str:
    return f"""
        你正在执行第二轮（或更高轮次）的字幕审校。

        【上一轮你提出的意见】：
        {review_feedback}

        【当前待审核的字幕内容】：
        {content}

        请结合音频，判断上述意见是否已被完美执行。
        如果已解决所有问题，请回复“【校验通过】”。
        如果仍有问题，请明确指出，格式如下：
        - [序号] 时间戳：{{"原文内容"}} -> 修改建议：{{"修正后的内容"}}
        """


# 2. resource(s)
# 2-1. get_subtitle_content
@mcp.resource(uri="mcp://file/subtitle/{file_path}", mime_type="text/plain")
def get_subtitle_content(file_path: str) -> str:
    try:
        if not os.path.exists(file_path):
            return f"错误：找不到字幕文件 {file_path}"

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return content
    except Exception as e:
        return f"读取字幕内容失败: {str(e)}"


# 3. tool(s)
# 3-1. ffmpeg_extract_audio
@mcp.tool()
def ffmpeg_extract_audio(video_path: str) -> str:
    """
    提取视频文件中的音频并保存为 WAV 格式。

    Args:
        video_path: 输入视频文件的完整路径。
    Returns:
        生成的 MP3 文件的路径, 以 .mp3 结尾
    """
    try:
        logger.info(f'[MCP tool] 提取音频: {video_path}')
        output_dir = settings.AUDIO_PATH

        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 处理文件名：去掉原后缀，加上.wav
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        audio_path = os.path.join(output_dir, f'{base_name}.mp3')
        (
            ffmpeg
            .input(video_path)
            .output(
                audio_path,
                acodec='libmp3lame',
            )
            .overwrite_output()  # 如果文件存在则覆盖
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f'[MCP tool] 提取音频成功，mp3文件保存至: {audio_path}')
        return audio_path
    except ffmpeg.Error as e:
        logger.error(f'[MCP tool] 提取音频失败：{str(e)}')
        return f'Error: 音频提取失败 - {e.stderr.decode()}'


# 3-2. whisper_speech_to_text
@mcp.tool()
def whisper_speech_to_text(audio_path: str, initial_prompt: str = "") -> str:
    """
    使用 Whisper 模型将音频文件转录为 SRT 字幕文件。

    Args:
        audio_path: 输入音频文件 (.mp3) 的绝对路径。
        initial_prompt: 可选的引导词，用于规范术语拼写或设定转录风格。
    Returns:
        生成的 .srt 字幕文件的绝对路径。
    """
    try:
        logger.info(f'[MCP tool] 开始转录音频: {audio_path}')

        # 1. 获取全局唯一的模型实例
        model = get_whisper()

        # 2. 执行转录
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,         # beam_size=5 是精度与速度的平衡点
            initial_prompt=initial_prompt,
            vad_filter=True      # 自动过滤静音，避免无效字幕
        )

        # 3. 准备输出路径
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        original_srt_path = os.path.join(settings.ORIGINAL_SRT_PATH, f'{base_name}.srt')

        os.makedirs(os.path.dirname(original_srt_path), exist_ok=True)

        # 4. 写入 SRT 文件
        with open(original_srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = format_srt_timestamp(segment.start)
                end_time = format_srt_timestamp(segment.end)
                print(f"正在处理: {segment.text}")
                text = segment.text.strip()

                # 写入标准 SRT 格式块
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

        logger.info(f"[MCP tool] 转录完成，SRT 已保存：{original_srt_path}")
        return original_srt_path
    except Exception as e:
        logger.error(f"[MCP tool] 转录失败：{str(e)}")
        return f"Error: 转录失败 - {str(e)}"

# 3-3. save_subtitle_tool
@mcp.tool()
def save_subtitle_tool(file_path: str, content: str) -> str:
    """
    将 LLM 优化或重写后的字幕文本内容保存为新的 .srt 文件。

    Args:
        file_path: .srt 字幕文件
        content: 经过 LLM 修正后的完整 SRT 格式字符串
    Returns:
        重写后的 .srt 字幕文件的绝对路径。
    """
    try:
        logger.info(f"[MCP tool] 开始重写: {file_path}")
        basename = os.path.basename(file_path)

        final_srt_path = os.path.join(settings.FINAL_SRT_PATH, basename)

        os.makedirs(os.path.dirname(final_srt_path), exist_ok=True)

        with open(final_srt_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"[MCP tool] 重写完成！，保存至: {final_srt_path}")
        return final_srt_path

    except Exception as e:
        logger.error(f"[MCP tool] 重写失败: {str(e)}")
        return f"Error: 重写失败 - {str(e)}"


# 3-4. ffmpeg_burn_subtitles
@mcp.tool()
def ffmpeg_burn_subtitles(video_path: str, srt_path: str) -> str:
    """
    使用 ffmpeg 将指定的 SRT 字幕文件硬压（Burn-in）到视频中。

    Args:
        video_path: 原始视频文件的绝对路径。
        srt_path: 经过修正后的 .srt 字幕文件的绝对路径。
    Returns:
        生成的带字幕视频的绝对路径。
    """
    try:
        logger.info(f'[MCP tool] 开始压制字幕: {video_path}')

        # 1. 准备输出路径
        os.makedirs(settings.FINAL_VIDEO_PATH, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        extension = os.path.splitext(video_path)[1]

        final_video_path = os.path.join(settings.FINAL_VIDEO_PATH, f"{base_name}{extension}")

        # 2. 重要：处理 ffmpeg subtitles 滤镜的路径转义
        # 在 Windows 下，路径如 C:\path\to.srt 必须处理成 C\:/path/to.srt
        safe_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")

        # 3. 执行 ffmpeg 指令
        (
            ffmpeg
            .input(video_path)
            .output(
                final_video_path,
                vf=f"subtitles='{safe_srt_path}'",
                vcodec="libx264",       # 视频使用 H.264 重新编码
                acodec="copy",          # 音频直接流拷贝，不重编
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f'[MCP tool] 字幕压制成功: {final_video_path}')

        return final_video_path


    except ffmpeg.Error as e:
        # 提取 ffmpeg 的错误日志
        logger.error(f'[MCP tool] 字幕压制失败: {str(e)}')
        return f"Error: 压制失败 - {str(e)}"

# 3-5. web_search
@mcp.tool()
def web_search(query: str) -> str:
    """
    联网检索工具 - 使用 Tavily 进行深度搜索

    Args:
        query:搜索查询关键词
    Returns:
        包含搜索结果的字典，包括答案和详细来源
    """
    try:
        logger.info(f"[MCP Tool] 执行 联网查询：{query}")
        response = tavily_client.invoke(input=query)
        result = response.get("answer", "未找到相关内容。")

        logger.info(f"[MCP search tool] 完成，基础答案: {result}")
        return result
    except Exception as e:
        logger.error(f"[MCP tool] 搜索失败：{str(e)}")
        return "联网搜索失败！"

# 3-6. get_time
@mcp.tool()
def get_time() -> str:
    """
    获取当前时间
    Returns:
        当前时间的字符串表示，格式为 "YYYY-MM-DD HH:MM:SS"
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_mcp_server():
    """运行MCP服务器"""
    logger.info(f"🚀 启动MCP服务器: {settings.MCP_SERVER_NAME}")
    logger.info("=" * 60)
    logger.info("可用工具:")
    logger.info("  - ffmpeg_extract_audio: 提取视频文件中的音频并保存为 WAV 格式。")
    logger.info("  - whisper_speech_to_text: 使用 Whisper 模型将音频文件转录为 SRT 字幕文件。")
    logger.info("  - save_subtitle_tool: 将 LLM 优化或重写后的字幕文本内容保存为新的 .srt 文件。")
    logger.info("  - ffmpeg_burn_subtitles: 使用 ffmpeg 将指定的 SRT 字幕文件硬压（Burn-in）到视频中。")
    logger.info("  - web_search: 联网搜索。")
    logger.info("  - get_time: 获取当前时间。")
    logger.info("=" * 60)

    mcp.run(
        transport='streamable-http',
        host='127.0.0.1',
        port=9090,
        path='/mcp'
    )

if __name__ == '__main__':
    run_mcp_server()


